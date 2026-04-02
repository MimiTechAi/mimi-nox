"""
◑ MiMi Nox – ReAct / Reflexion Engine
core/react.py

ReAct = Reason + Act + Observe + Reflect

Ablauf:
  1. Antwort generieren (via chat_with_tools – inkl. Tool-Calls)
  2. Reflexion: Ist die Antwort vollständig und korrekt?
  3. Falls needs_revision=True UND Revisionen < MAX_REVISIONS:
     → Neu generieren mit Kritik als Kontext
  4. Finale Antwort zurückgeben

Design-Entscheidungen:
  - MAX_REVISIONS = 2 (nicht mehr, klares Limit)
  - Reflexion via separatem, schnellem LLM-Aufruf ohne Tools
  - reflect() ist unabhängig testbar (kein Seiteneffekt)
  - react_loop() ist thin wrapper über chat_with_tools
  - on_step Callback für UI-Transparenz (zeigt Revisionen an)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import ollama

from core.chat import chat_with_tools, OllamaNotReachableError, OllamaModelNotFoundError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_REVISIONS = 2

REFLEXION_SYSTEM_PROMPT = """Du bist ein präziser Qualitätsprüfer für KI-Antworten.

Deine Aufgabe: Beurteile ob eine gegebene Antwort korrekt und vollständig ist.

Antworte NUR mit:
  - Einer Bewertung (1-2 Sätze)
  - Genau einer dieser Zeilen:
      REVISION: JA   (wenn Antwort unvollständig/falsch/irreführend)
      REVISION: NEIN (wenn Antwort korrekt und ausreichend vollständig)
  - Falls JA: ein Satz Begründung nach "Grund: "

Sei streng aber fair. Kurze Antworten die die Frage vollständig beantworten sind OK.
"Ich weiß es nicht" ist IMMER eine schlechte Antwort wenn mehr möglich wäre.
"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ReflexionResult:
    """Ergebnis eines Reflexions-Schritts."""
    needs_revision: bool
    reason: str = ""


@dataclass
class ReActStep:
    """Ein einzelner Schritt im ReAct-Loop (für on_step Callback)."""
    iteration: int
    answer: str
    reflexion: ReflexionResult
    was_revised: bool = False


# ---------------------------------------------------------------------------
# reflect()
# ---------------------------------------------------------------------------

async def reflect(
    response: str,
    question: str,
    model: str,
) -> ReflexionResult:
    """
    Bewertet eine Antwort via einem separaten LLM-Aufruf.

    Nutzt kein Tool-Calling — nur puren Text-Output.
    Schnell, deterministisch, für post-hoc Qualitätsprüfung.

    Args:
        response: Die zu bewertende Antwort
        question: Die ursprüngliche Frage
        model:    Ollama-Modell (dasselbe wie für die Antwort)

    Returns:
        ReflexionResult(needs_revision=bool, reason=str)
        Gibt bei Fehler immer needs_revision=False zurück (fail safe).
    """
    client = ollama.AsyncClient()

    prompt = (
        f"Frage: {question}\n\n"
        f"Antwort zur Bewertung:\n{response}\n\n"
        f"Ist diese Antwort korrekt und vollständig?"
    )

    try:
        raw = await client.chat(
            model=model,
            messages=[
                {"role": "system", "content": REFLEXION_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            stream=False,
        )
        content: str = raw.message.content or ""
    except Exception:
        # Bei Fehler: keine Revision (fail safe – Antwort trotzdem ausgeben)
        return ReflexionResult(needs_revision=False, reason="")

    return _parse_reflexion(content)


def _parse_reflexion(content: str) -> ReflexionResult:
    """
    Parst den Reflexions-Output.

    Erwartet "REVISION: JA" oder "REVISION: NEIN" im Text.
    Fällt auf needs_revision=False zurück wenn keine eindeutige Aussage.
    """
    upper = content.upper()

    if "REVISION: JA" in upper or "REVISION:JA" in upper:
        # Begründung extrahieren
        reason_match = re.search(r"Grund:\s*(.+)", content, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else content[:100]
        return ReflexionResult(needs_revision=True, reason=reason)

    # "REVISION: NEIN" oder alles andere → keine Revision nötig
    return ReflexionResult(needs_revision=False, reason="")


# ---------------------------------------------------------------------------
# react_loop()
# ---------------------------------------------------------------------------

async def react_loop(
    question: str,
    model: str,
    context: list[dict] | None = None,
    on_step: Callable[[ReActStep], None] | None = None,
    on_chunk: Callable[[str], None] | None = None,
    on_tool_start: Callable[[str, dict], None] | None = None,
    on_tool_done: Callable[[str, str], None] | None = None,
) -> str:
    """
    ReAct-Loop mit Reflexions-basierter Selbstkorrektur.

    Ablauf pro Iteration:
      1. chat_with_tools() → Antwort (inkl. Tool-Calls wenn nötig)
      2. reflect()         → Ist die Antwort gut genug?
      3. Falls nicht:      → Neuer Versuch mit Kritik als Kontext
      4. nach MAX_REVISIONS: → Beste bisherige Antwort ausgeben

    Args:
        question:      Die User-Frage
        model:         Ollama-Modell
        context:       Optionale Konversations-History (Messages)
        on_step:       Callback nach jeder Iteration
        on_chunk:      Streaming Callback (letzte Iteration)
        on_tool_start: Tool-Start Callback
        on_tool_done:  Tool-Done Callback

    Returns:
        Beste generierte Antwort als String.

    Raises:
        OllamaNotReachableError:  Ollama nicht erreichbar
        OllamaModelNotFoundError: Modell nicht installiert
    """
    history: list[dict] = list(context or [])
    history.append({"role": "user", "content": question})

    last_answer = ""
    chunks_buffer: list[str] = []

    for iteration in range(1, MAX_REVISIONS + 2):  # +2: initial + MAX_REVISIONS
        is_last_iteration = iteration > MAX_REVISIONS
        chunks_buffer = []

        # Streaming nur in der letzten Iteration an on_chunk weiterleiten
        def _on_chunk(chunk: str, _iter: int = iteration) -> None:
            chunks_buffer.append(chunk)
            if _iter > 1 and on_chunk is not None:
                on_chunk(chunk)

        # Erste Iteration: kein on_chunk (wir wollen erst reflektieren)
        # Letzte Iteration: on_chunk weiterleiten für Streaming
        chunk_cb = on_chunk if is_last_iteration else _on_chunk

        answer = await chat_with_tools(
            model=model,
            history=history,
            on_chunk=chunk_cb if not is_last_iteration else (on_chunk or _on_chunk),
            on_tool_start=on_tool_start,
            on_tool_done=on_tool_done,
        )

        last_answer = answer or "".join(chunks_buffer)

        # Reflexion
        reflexion = await reflect(
            response=last_answer,
            question=question,
            model=model,
        )

        step = ReActStep(
            iteration=iteration,
            answer=last_answer,
            reflexion=reflexion,
            was_revised=(iteration > 1),
        )

        if on_step is not None:
            on_step(step)

        # Abbruch-Bedingungen
        if not reflexion.needs_revision:
            break

        if is_last_iteration:
            # Maximale Revisionen erreicht – beste Antwort zurückgeben
            break

        # Revision vorbereiten: Kritik als Kontext hinzufügen
        history.append({"role": "assistant", "content": last_answer})
        history.append({
            "role": "user",
            "content": (
                f"Deine Antwort war unvollständig oder fehlerhaft.\n"
                f"Kritik: {reflexion.reason}\n\n"
                f"Bitte gib eine verbesserte, vollständige Antwort."
            ),
        })

    return last_answer
