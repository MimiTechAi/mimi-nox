"""
◑ MiMi Nox – Skill Builder
core/skill_builder.py

Automatisierte Skill-Erstellung: Die KI scannt den Code-Stil des Users,
generiert einen neuen Skill im Markdown-Format und speichert ihn.

Sicherheitsmaßnahmen:
  - XML-Tag-Extraktion (kein Smalltalk in der .md-Datei)
  - Path-Traversal-Schutz (Sandbox auf SKILLS_DIR)
  - Überschreib-Schutz (automatische Versionierung: -v2, -v3)
  - Kontext-Limit (max 5 Dateien scannen)
  - Few-Shot Meta-Prompt (writer.md als Referenz)

MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from core.chat import chat_with_tools
from core.skills import (
    SkillLoader,
    Skill,
    _parse_skill,
    SkillLoadError,
    BUILTIN_SKILLS_DIR,
)


# ── Scan-Limit ──────────────────────────────────────────────────────────────

MAX_SCAN_FILES = 5  # Maximal 5 Dateien scannen → verhindert Token-Explosion


# ── Few-Shot Referenz laden ─────────────────────────────────────────────────

def _load_reference_skill() -> str:
    """Lädt writer.md als Few-Shot-Beispiel für den Meta-Prompt."""
    ref = BUILTIN_SKILLS_DIR / "writer.md"
    if ref.exists():
        return ref.read_text(encoding="utf-8")
    return ""


# ── System-Prompt mit XML-Tags + Few-Shot ───────────────────────────────────

SKILL_BUILDER_SYSTEM = """\
Du bist der Skill-Builder von ◑ MiMi Nox. Deine Aufgabe: Erstelle einen neuen
Skill basierend auf einem Thema, das der User beschreibt.

## Was ist ein Skill?
Ein Skill ist eine Markdown-Datei im Verzeichnis ~/.mimi-nox/skills/.
Sie definiert eine spezialisierte KI-Rolle mit eigenem Trigger-Befehl.

## Projekt-Struktur (MiMi Nox)
```
core/         → Backend-Logik (chat.py, tools.py, skills.py, react.py)
server/       → FastAPI-Server (routes/chat.py, routes/memory.py)
app/src/      → Web-Frontend (index.html, main.js, style.css)
skills/       → Built-in Skills (writer.md, code-reviewer.md, etc.)
tests/        → TDD-Tests
```

## Referenz-Skill (EXAKT dieses Format nutzen!)
Hier ist ein perfektes Beispiel eines existierenden Skills:

{reference_skill}

## Dein Output-Format (STRIKT!)
Du MUSST deinen Output in XML-Tags verpacken:

1. Dateiname: <skill_filename>mein-skill.md</skill_filename>
2. Inhalt:    <new_skill_content>...der komplette Skill-Markdown...</new_skill_content>

Regeln:
- skill-name: lowercase mit Bindestrichen (z.B. fastapi-expert)
- Trigger: immer mit / beginnen, kurz (z.B. /fastapi)
- Description: maximal 1 Satz
- System Prompt: Präzise Rollenbeschreibung. Maximal 200 Wörter.
- Tools: Nur aus: web_search, read_file, list_directory, file_search, get_datetime, analyze_image
- Test: Einfacher Smoke-Test

## Kontext-Limit
Wenn du Code scannst, lies MAXIMAL {max_scan} Dateien. Das reicht um den Stil zu verstehen.

## WICHTIG
- Gib NUR die XML-Tags aus. Kein Smalltalk davor oder danach.
- Der Inhalt in <new_skill_content> muss EXAKT dem Referenz-Format folgen.
"""


# ── XML-Extraktion (Punkt 2: Output bändigen) ──────────────────────────────

def extract_skill_content(llm_output: str) -> str:
    """
    Extrahiert den Skill-Markdown-Content aus XML-Tags.

    Primär: <new_skill_content>...</new_skill_content>
    Fallback 1: ```markdown Code-Block
    Fallback 2: Output beginnt direkt mit '# '

    Returns:
        Der reine Skill-Markdown-Content (ohne Smalltalk)

    Raises:
        SkillLoadError: kein extrahierbarer Content gefunden
    """
    # Primär: XML-Tag-Extraktion
    xml_match = re.search(
        r"<new_skill_content>\s*(.*?)\s*</new_skill_content>",
        llm_output,
        re.DOTALL,
    )
    if xml_match:
        return xml_match.group(1).strip()

    # Fallback 1: ```markdown Code-Block
    md_match = re.search(
        r"```(?:markdown|md)\s*\n(.*?)```",
        llm_output,
        re.DOTALL,
    )
    if md_match:
        return md_match.group(1).strip()

    # Fallback 2: Output beginnt direkt mit # (kein Wrapper)
    if llm_output.strip().startswith("# "):
        return llm_output.strip()

    raise SkillLoadError(
        "LLM-Output enthält weder <new_skill_content>-Tags noch einen "
        "```markdown Block.\n"
        f"Output (erste 200 Zeichen): {llm_output[:200]}"
    )


def extract_skill_filename(llm_output: str) -> str | None:
    """
    Extrahiert den gewünschten Dateinamen aus <skill_filename>-Tag.

    Returns:
        Dateiname (z.B. "fastapi-expert.md") oder None
    """
    match = re.search(
        r"<skill_filename>\s*(.*?)\s*</skill_filename>",
        llm_output,
    )
    if match:
        raw = match.group(1).strip()
        # Erst Basisname extrahieren (entfernt ../ und Verzeichnisse)
        basename = Path(raw).name
        # Dann nur sichere Zeichen behalten
        filename = re.sub(r"[^a-zA-Z0-9\-.]", "", basename)
        if filename and not filename.endswith(".md"):
            filename += ".md"
        return filename if filename else None
    return None


# Legacy-Alias für Kompatibilität mit bestehenden Tests
extract_skill_markdown = extract_skill_content


def extract_skill_name(markdown: str) -> str:
    """Extrahiert den Skill-Namen aus der Markdown H1-Zeile."""
    match = re.match(r"#\s+(.+)", markdown)
    if not match:
        raise SkillLoadError("Kein '# skill-name' Header gefunden.")
    return match.group(1).strip().lower().replace(" ", "-")


# ── Path-Traversal-Schutz (Punkt 1: Sandboxing) ────────────────────────────

def _validate_skill_path(skills_dir: Path, filename: str) -> Path:
    """
    Validiert den Zielpfad gegen Path-Traversal-Angriffe.

    Args:
        skills_dir: Erlaubtes Basis-Verzeichnis
        filename:   Gewünschter Dateiname

    Returns:
        Sicherer, absoluter Pfad

    Raises:
        SecurityError: wenn der Pfad außerhalb des skills_dir liegt
    """
    # Normalisieren
    safe_name = Path(filename).name  # Entfernt ../ und Verzeichnisse
    if not safe_name or safe_name.startswith("."):
        raise ValueError(f"Ungültiger Skill-Dateiname: '{filename}'")

    target = (skills_dir / safe_name).resolve()
    allowed = skills_dir.resolve()

    if not str(target).startswith(str(allowed)):
        raise PermissionError(
            f"Sicherheitsverletzung: '{target}' liegt außerhalb von '{allowed}'"
        )

    return target


# ── Überschreib-Schutz (Punkt 1b: Versionierung) ──────────────────────────

def _unique_skill_name(loader: SkillLoader, name: str) -> str:
    """
    Generiert einen einzigartigen Skill-Namen.
    Wenn 'fastapi-expert' existiert → 'fastapi-expert-v2', etc.

    Returns:
        Einzigartiger Name (ohne .md)
    """
    if not loader.is_user_skill(name) and not loader.is_builtin(name):
        return name

    for version in range(2, 100):
        candidate = f"{name}-v{version}"
        if not loader.is_user_skill(candidate) and not loader.is_builtin(candidate):
            return candidate

    raise SkillLoadError(f"Zu viele Versionen von Skill '{name}' (max 99).")


# ── Builder ──────────────────────────────────────────────────────────────────

async def build_skill(
    topic: str,
    model: str,
    on_phase: Callable[[str], None] | None = None,
    on_chunk: Callable[[str], None] | None = None,
    on_thinking: Callable[[str], None] | None = None,
    on_tool_start: Callable[[str, dict], None] | None = None,
    on_tool_done: Callable[[str, str], None] | None = None,
    skills_loader: SkillLoader | None = None,
) -> Skill:
    """
    Baut einen neuen Skill basierend auf einem Thema.

    Sicherheit:
      - Path-Traversal-Schutz (Sandboxing)
      - Überschreib-Schutz (automatische Versionierung)
      - XML-Extraktion (sauberer Output)
      - Kontext-Limit (max 5 Dateien)

    Args:
        topic:         Was der Skill können soll
        model:         Ollama Modell-Name
        on_phase:      Callback für Phasen-Updates
        on_chunk:      Callback für Text-Chunks
        on_thinking:   Callback für Thinking-Tokens
        on_tool_start: Callback wenn Tool startet
        on_tool_done:  Callback wenn Tool fertig
        skills_loader: Optional: SkillLoader-Instanz (für Tests)

    Returns:
        Das gespeicherte Skill-Objekt

    Raises:
        ValueError:       Leeres Topic
        SkillLoadError:   Generierter Skill ist ungültig
        PermissionError:  Path-Traversal-Versuch
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic darf nicht leer sein.")

    loader = skills_loader or SkillLoader()

    # ── Phase 1+2: Scan + Generierung ────────────────────────────────────
    if on_phase:
        on_phase("📚 Code-Muster analysieren…")

    # Few-Shot Referenz laden
    reference = _load_reference_skill()

    # System-Prompt mit Referenz und Scan-Limit befüllen
    system = SKILL_BUILDER_SYSTEM.format(
        reference_skill=reference,
        max_scan=MAX_SCAN_FILES,
    )

    # Sammle den gesamten LLM-Output
    output_chunks: list[str] = []

    def _collect_chunk(chunk: str) -> None:
        output_chunks.append(chunk)
        if on_chunk:
            on_chunk(chunk)

    user_prompt = (
        f"Erstelle einen neuen Skill für folgendes Thema:\n\n"
        f"**{topic}**\n\n"
        f"Scanne zuerst maximal {MAX_SCAN_FILES} relevante Dateien im Projekt "
        f"um den Code-Stil zu verstehen (nutze list_directory und read_file). "
        f"Dann generiere den Skill in den XML-Tags "
        f"<skill_filename> und <new_skill_content>."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    await chat_with_tools(
        model=model,
        history=messages,
        on_chunk=_collect_chunk,
        on_thinking=on_thinking,
        on_tool_start=on_tool_start,
        on_tool_done=on_tool_done,
        on_phase=on_phase,
    )

    full_output = "".join(output_chunks)

    # ── Phase 3: XML-Extraktion + Validierung + Speichern ────────────────
    if on_phase:
        on_phase("💾 Skill speichern…")

    # Content aus XML-Tags extrahieren (kein Smalltalk!)
    skill_markdown = extract_skill_content(full_output)

    # Name extrahieren
    name = extract_skill_name(skill_markdown)

    # Parsen zur Validierung (vor dem Speichern!)
    parsed = _parse_skill(name, skill_markdown)

    # Überschreib-Schutz: einzigartigen Namen generieren
    unique_name = _unique_skill_name(loader, parsed.name)
    if unique_name != parsed.name:
        if on_phase:
            on_phase(f"📝 Name '{parsed.name}' existiert → '{unique_name}'")
        parsed = Skill(
            name=unique_name,
            trigger=parsed.trigger if unique_name == parsed.name else f"/{unique_name}",
            description=parsed.description,
            system_prompt=parsed.system_prompt,
            tools=parsed.tools,
            test=parsed.test,
        )

    # Path-Traversal-Schutz: Pfad validieren
    _validate_skill_path(loader._user_dir, f"{parsed.name}.md")

    # Atomar speichern via SkillLoader
    saved_skill = loader.save(
        name=parsed.name,
        trigger=parsed.trigger,
        description=parsed.description,
        tools=parsed.tools,
        system_prompt=parsed.system_prompt,
    )

    return saved_skill
