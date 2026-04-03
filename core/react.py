"""
◑ MiMi Nox – ReAct / Reflexion Engine
core/react.py

ReAct = Reason + Act + Observe + Reflect

Ablauf:
  1. Antwort generieren (via chat_with_tools – inkl. Tool-Calls) → intern puffern
  2. Reflexion: Ist die Antwort vollständig und korrekt?
  3. Falls needs_revision=True UND unter MAX_REVISIONS: Revision vorbereiten, goto 1
  4. Finale Antwort via on_chunk streamen + zurückgeben

Design-Entscheidungen:
  - MAX_REVISIONS = 2 (streng, kein infinite loop)
  - Alle Zwischen-Iterationen: gepuffert (kein Streaming in UI)
  - Nur finale Antwort wird via on_chunk an UI gesendet
  - reflect() wird NICHT nach der letzten Iteration aufgerufen (Performance)
  - on_step Callback nach jeder Iteration für volle Transparenz
  - reflect(): fail-safe (Exception → needs_revision=False)
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
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
  - Einer kurzen Bewertung (1-2 Sätze)
  - Genau einer dieser Zeilen:
      REVISION: JA   (wenn Antwort unvollständig, falsch oder irreführend)
      REVISION: NEIN (wenn Antwort korrekt und ausreichend vollständig)
  - Falls JA: ein Satz Begründung nach "Grund: "

Sei streng aber fair. Kurze Antworten die die Frage vollständig beantworten sind OK.
"Ich weiß es nicht" ist IMMER schlecht wenn Tools verfügbar sind.
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
    Bewertet eine Antwort via separatem LLM-Aufruf.

    Kein Tool-Calling — purer Text-Output.
    Fail-safe: bei jedem Fehler → needs_revision=False (Antwort trotzdem ausgeben).

    Args:
        response: Die zu bewertende Antwort
        question: Die ursprüngliche Frage
        model:    Ollama-Modell

    Returns:
        ReflexionResult(needs_revision=bool, reason=str)
    """
    client = ollama.AsyncClient()

    prompt = (
        f"Frage: {question}\n\n"
        f"Antwort zur Bewertung:\n{response}\n\n"
        f"Ist diese Antwort korrekt und vollständig?"
    )

    try:
        raw = await asyncio.wait_for(
            client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": REFLEXION_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                stream=False,
            ),
            timeout=30.0,
        )
        content: str = raw.message.content or ""
    except Exception:
        return ReflexionResult(needs_revision=False, reason="")

    return _parse_reflexion(content)


def _parse_reflexion(content: str) -> ReflexionResult:
    """
    Parst Reflexions-Output.
    Erwartet 'REVISION: JA' oder 'REVISION: NEIN'.
    Fällt auf needs_revision=False zurück wenn kein klares Signal.
    """
    upper = content.upper()

    if "REVISION: JA" in upper or "REVISION:JA" in upper:
        reason_match = re.search(r"Grund:\s*(.+)", content, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else content[:120].strip()
        return ReflexionResult(needs_revision=True, reason=reason)

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

    GARANTIEN:
      - Terminiert immer (max MAX_REVISIONS + 1 Iterationen)
      - on_chunk wird NUR für die finale Antwort aufgerufen (keine Doppelausgabe)
      - reflect() wird NICHT nach der letzten Iteration aufgerufen (Performance)
      - Alle Exceptions (OllamaNotReachable, OllamaModelNotFound, Shell) propagieren

    Ablauf:
      Iteration 1..MAX_REVISIONS:
        a) chat_with_tools() → Antwort intern puffern (kein on_chunk)
        b) reflect() → needs_revision?
        c) Ja → Revision-Kontext aufbauen, weiter
        d) Nein → finale Antwort, Abbruch
      Iteration MAX_REVISIONS+1 (Sicherheitsnetz):
        a) chat_with_tools() → Antwort via on_chunk streamen (letzte Chance)
        b) reflect() NICHT mehr aufrufen

    Args:
        question:      User-Frage (letztes Element der History)
        model:         Ollama-Modell
        context:       History OHNE die aktuelle Frage
        on_step:       Callback nach jeder Iteration (Transparenz)
        on_chunk:      Streaming Callback NUR für finale Antwort
        on_tool_start: Tool-Start Callback (alle Iterationen)
        on_tool_done:  Tool-Done Callback (alle Iterationen)

    Returns:
        Beste generierte Antwort als String.

    Raises:
        OllamaNotReachableError:   Ollama nicht erreichbar
        OllamaModelNotFoundError:  Modell nicht installiert
        ShellConfirmationRequired: Shell braucht User-Bestätigung
    """
    history: list[dict] = list(context or [])
    history.append({"role": "user", "content": question})

    last_answer = ""
    max_iterations = MAX_REVISIONS + 1  # initial + max revisions

    for iteration in range(1, max_iterations + 1):
        is_final_iteration = iteration == max_iterations

        # ── Streaming-Strategie ─────────────────────────────────────────────
        # Zwischen-Iterationen: intern puffern, KEIN on_chunk an UI
        # Letzte Iteration (Sicherheitsnetz): on_chunk direkt
        # Normale finale Iteration (reflexion=False): Replay nach dem Loop
        iteration_buffer: list[str] = []

        def _buffer_chunk(chunk: str, buf: list[str] = iteration_buffer) -> None:
            buf.append(chunk)

        chunk_cb = on_chunk if is_final_iteration else _buffer_chunk

        # ── LLM-Aufruf ─────────────────────────────────────────────────────
        answer = await chat_with_tools(
            model=model,
            history=history,
            on_chunk=chunk_cb,
            on_tool_start=on_tool_start,
            on_tool_done=on_tool_done,
        )

        last_answer = answer or "".join(iteration_buffer)

        # ── Reflexion (NICHT nach letzter Iteration — Performance) ──────────
        if is_final_iteration:
            # Sicherheitsnetz: Antwort bereits via on_chunk gestreamt
            step = ReActStep(
                iteration=iteration,
                answer=last_answer,
                reflexion=ReflexionResult(needs_revision=False, reason=""),
                was_revised=True,
            )
            if on_step is not None:
                on_step(step)
            break

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

        if not reflexion.needs_revision:
            # Antwort ist gut → via on_chunk an UI senden (Replay des Puffers)
            if on_chunk is not None:
                for chunk in iteration_buffer:
                    on_chunk(chunk)
            break

        # ── Revision vorbereiten ──────────────────────────────────────────
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
