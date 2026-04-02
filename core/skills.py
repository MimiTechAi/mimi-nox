"""
◑ MiMi Nox – Skills System
core/skills.py

Lädt und testet Markdown-basierte Skills.

Skill-Format (Markdown):
  # skill-name
  **Trigger**: /trigger
  **Description**: Beschreibung
  **Tools**: tool1, tool2

  ## System Prompt
  Du bist ein...

  ## Test
  **Input**: Test-Eingabe
  **Expect Tool**: tool_name
  **Expect Contains**: erwarteter Text

Skill-Verzeichnisse (Priorität):
  1. ~/.mimi-nox/skills/     (Nutzer-Skills)
  2. skills/                 (Built-in Skills im Repo)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

DEFAULT_USER_SKILLS_DIR = Path.home() / ".mimi-nox" / "skills"
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SkillTest:
    """Test-Definition innerhalb eines Skills."""
    input: str = ""
    expect_tool: str = ""
    expect_contains: str = ""


@dataclass
class Skill:
    """Geladenes Skill-Objekt."""
    name: str
    trigger: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    test: SkillTest = field(default_factory=SkillTest)


@dataclass
class SkillTestResult:
    """Ergebnis eines Skill-Tests."""
    skill_name: str
    passed: bool
    message: str = ""
    tool_called: str = ""
    response: str = ""


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class SkillLoadError(Exception):
    """Skill-Datei ungültig oder nicht gefunden."""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_skill(name: str, content: str) -> Skill:
    """
    Parst eine Markdown-Skill-Datei.

    Raises:
        SkillLoadError: wenn Pflichtfelder fehlen
    """
    # Trigger
    trigger_match = re.search(r"\*\*Trigger\*\*:\s*(\S+)", content)
    if not trigger_match:
        raise SkillLoadError(
            f"Skill '{name}': Fehlendes Pflichtfeld '**Trigger**:'"
        )

    # Description
    desc_match = re.search(r"\*\*Description\*\*:\s*(.+)", content)
    description = desc_match.group(1).strip() if desc_match else ""

    # Tools
    tools_match = re.search(r"\*\*Tools\*\*:\s*(.+)", content)
    tools: list[str] = []
    if tools_match:
        tools = [t.strip() for t in tools_match.group(1).split(",") if t.strip()]

    # System Prompt (zwischen ## System Prompt und ## Test oder Ende)
    sp_match = re.search(
        r"##\s+System Prompt\s*\n(.*?)(?=##|\Z)",
        content,
        re.DOTALL,
    )
    if not sp_match:
        raise SkillLoadError(
            f"Skill '{name}': Fehlender '## System Prompt' Block"
        )
    system_prompt = sp_match.group(1).strip()
    if not system_prompt:
        raise SkillLoadError(
            f"Skill '{name}': System Prompt ist leer"
        )

    # Test Block (optional)
    skill_test = SkillTest()
    test_block_match = re.search(r"##\s+Test\s*\n(.*?)(?:\Z)", content, re.DOTALL)
    if test_block_match:
        tb = test_block_match.group(1)
        inp = re.search(r"\*\*Input\*\*:\s*(.+)", tb)
        exp_tool = re.search(r"\*\*Expect Tool\*\*:\s*(\S+)", tb)
        exp_contains = re.search(r"\*\*Expect Contains\*\*:\s*(.+)", tb)

        skill_test = SkillTest(
            input=inp.group(1).strip() if inp else "",
            expect_tool=exp_tool.group(1).strip() if exp_tool else "",
            expect_contains=exp_contains.group(1).strip() if exp_contains else "",
        )

    return Skill(
        name=name,
        trigger=trigger_match.group(1).strip(),
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        test=skill_test,
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class SkillLoader:
    """
    Lädt Skills aus Markdown-Dateien.

    Sucht in:
      1. skills_dir (Nutzer-Skills, Standard: ~/.mimi-nox/skills/)
      2. BUILTIN_SKILLS_DIR (Built-in Skills im Repo)
    """

    def __init__(
        self,
        skills_dir: Path | None = None,
        builtin_dir: Path | None = None,
    ) -> None:
        self._user_dir = Path(skills_dir or DEFAULT_USER_SKILLS_DIR)
        self._builtin_dir = Path(builtin_dir or BUILTIN_SKILLS_DIR)

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, name: str) -> Skill:
        """
        Lädt einen Skill per Name.

        Sucht: {name}.md in user_dir, dann builtin_dir.

        Raises:
            SkillLoadError: wenn Datei nicht gefunden oder ungültig
        """
        for directory in [self._user_dir, self._builtin_dir]:
            path = directory / f"{name}.md"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return _parse_skill(name, content)

        raise SkillLoadError(
            f"Skill '{name}' nicht gefunden in:\n"
            f"  {self._user_dir}/{name}.md\n"
            f"  {self._builtin_dir}/{name}.md"
        )

    def load_all(self) -> list[Skill]:
        """
        Lädt alle verfügbaren Skills aus beiden Verzeichnissen.
        Überspringe fehlerhafte Dateien (kein Crash).

        Returns:
            Liste aller gültigen Skills.
        """
        skills: list[Skill] = []
        seen_names: set[str] = set()

        for directory in [self._user_dir, self._builtin_dir]:
            if not directory.exists():
                continue
            for md_file in sorted(directory.glob("*.md")):
                name = md_file.stem
                if name in seen_names:
                    continue  # Nutzer-Skill hat Vorrang, nicht nochmal laden
                try:
                    skill = _parse_skill(name, md_file.read_text(encoding="utf-8"))
                    skills.append(skill)
                    seen_names.add(name)
                except SkillLoadError:
                    continue  # Fehlerhafte Datei überspringen

        return skills

    def resolve_trigger(self, trigger: str) -> Skill | None:
        """
        Findet einen Skill anhand seines Triggers.

        Returns:
            Skill-Objekt oder None wenn kein Trigger passt.
        """
        for skill in self.load_all():
            if skill.trigger == trigger:
                return skill
        return None

    async def run_test(self, name: str) -> SkillTestResult:
        """
        Führt den Selbst-Test eines Skills durch.

        Nutzt chat_with_tools mit dem Skill als System-Prompt.
        Prüft ob das erwartete Tool aufgerufen wurde.

        Returns:
            SkillTestResult (passed = True/False)
        """
        from core.chat import chat_with_tools, OllamaNotReachableError
        from core.tools import get_tool_schemas

        # Skill laden
        try:
            skill = self.load(name)
        except SkillLoadError as exc:
            return SkillTestResult(
                skill_name=name,
                passed=False,
                message=f"Skill konnte nicht geladen werden: {exc}",
            )

        if not skill.test.input:
            return SkillTestResult(
                skill_name=name,
                passed=True,
                message="Kein Test definiert (übersprungen).",
            )

        # Ollama-Aufruf mit Skill-System-Prompt
        tool_called: list[str] = []
        chunks: list[str] = []

        history = [
            {"role": "system", "content": skill.system_prompt},
            {"role": "user",   "content": skill.test.input},
        ]

        try:
            import os
            model = os.environ.get("MIMI_NOX_MODEL", "phi4-mini")
            response = await chat_with_tools(
                model=model,
                history=history,
                on_chunk=chunks.append,
                on_tool_start=lambda n, _: tool_called.append(n),
            )
        except OllamaNotReachableError:
            return SkillTestResult(
                skill_name=name,
                passed=False,
                message="Ollama nicht erreichbar – Test übersprungen.",
            )
        except Exception as exc:
            return SkillTestResult(
                skill_name=name,
                passed=False,
                message=f"Fehler während Test: {exc}",
            )

        full_response = response or "".join(chunks)

        # Prüfungen
        if skill.test.expect_tool and skill.test.expect_tool not in tool_called:
            return SkillTestResult(
                skill_name=name,
                passed=False,
                message=(
                    f"Erwartet Tool '{skill.test.expect_tool}' aber aufgerufen: "
                    f"{tool_called or 'keines'}"
                ),
                tool_called=", ".join(tool_called),
                response=full_response[:200],
            )

        if skill.test.expect_contains:
            if skill.test.expect_contains.lower() not in full_response.lower():
                return SkillTestResult(
                    skill_name=name,
                    passed=False,
                    message=(
                        f"Antwort enthält nicht '{skill.test.expect_contains}'"
                    ),
                    tool_called=", ".join(tool_called),
                    response=full_response[:200],
                )

        return SkillTestResult(
            skill_name=name,
            passed=True,
            message="Test bestanden.",
            tool_called=", ".join(tool_called),
            response=full_response[:200],
        )
