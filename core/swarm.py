"""
◑ MiMi Nox – Swarm Engine

Multi-agent pipeline that distributes a task across specialized LLM agents:

    /swarm <task>

    ┌──────────────┐
    │   PLANER     │  gemma4:e4b: zerlegt Aufgabe in Teilaufgaben
    └──────┬───────┘
           │ N Teilaufgaben
    ┌──────▼─────────────────────────────┐
    │          asyncio.gather()           │   ← PARALLEL
    │  Agent1    Agent2    Agent3 ...     │
    └──────┬─────────────────────────────┘
           │ N Teilergebnisse
    ┌──────▼───────┐
    │  SYNTHESIZER │  fasst alles zu einer kohärenten Antwort
    └──────────────┘

Design rules (same as chat.py):
- Pure async Python, no Textual imports
- on_progress callback for streaming UI updates
- Raises OllamaNotReachableError / OllamaModelNotFoundError as needed

MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable

import ollama

from core.chat import OllamaModelNotFoundError, OllamaNotReachableError
from core.types import Message

# Max parallel specialist agents – optimized for E4B (~4B active params, ~3GB each)
MAX_SPECIALISTS = 3


# ── Prompts ───────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """\
You are a task planner. Given a task, break it into 2-4 clear, independent subtasks.
Return ONLY a JSON array of strings. No explanation, no markdown, just JSON.
Example: ["Design the data model", "Write the API endpoints", "Add error handling"]
"""

SPECIALIST_SYSTEM = """\
You are a specialist agent. Complete the given subtask concisely and precisely.
Focus only on your assigned subtask. Be direct and practical.
"""

SYNTHESIZER_SYSTEM = """\
You are a synthesis agent. Combine multiple specialist outputs into one coherent,
well-structured response. Avoid duplication. Be clear and actionable.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_client() -> ollama.AsyncClient:
    return ollama.AsyncClient()


def _wrap_exc(exc: Exception) -> Exception:
    """Convert low-level connection errors to our custom exceptions."""
    msg = str(exc).lower()
    if any(k in msg for k in ("connection", "refused", "socket", "connect")):
        return OllamaNotReachableError()
    if "not found" in msg or "does not exist" in msg:
        return exc  # let caller extract model name
    return exc


async def _call_model(
    system: str,
    user: str,
    model: str,
) -> str:
    """Single non-streaming model call. Returns the response text."""
    client = _make_client()
    try:
        response = await asyncio.wait_for(
            client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=False,
            ),
            timeout=45.0,
        )
        return str(response["message"]["content"]).strip()
    except Exception as exc:
        raise _wrap_exc(exc) from exc


# ── Core pipeline ─────────────────────────────────────────────────────────────

async def _plan(task: str, model: str) -> list[str]:
    """
    Step 1: Planner – break the task into subtasks.
    Returns a list of subtask strings (2–4 items).
    Falls back to [task] if parsing fails (fail-safe).
    """
    raw = await _call_model(PLANNER_SYSTEM, task, model)

    # Try to extract JSON array
    try:
        # Handle model wrapping JSON in markdown code block
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            subtasks = json.loads(match.group())
            if isinstance(subtasks, list) and len(subtasks) > 0:
                return [str(s) for s in subtasks[:MAX_SPECIALISTS]]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: treat whole response as single task
    return [task]


async def _run_specialist(
    subtask: str,
    original_task: str,
    model: str,
    index: int,
    on_progress: Callable[[str], None] | None,
) -> str:
    """
    Step 2: Specialist – handle one subtask.
    Calls on_progress with live status text.
    """
    if on_progress:
        on_progress(f"  [{index+1}] {subtask[:60]}…")

    context = f"Main task: {original_task}\n\nYour subtask: {subtask}"
    result = await _call_model(SPECIALIST_SYSTEM, context, model)

    if on_progress:
        on_progress(f"  [{index+1}] ✓ done")

    return result


async def _synthesize(
    task: str,
    subtasks: list[str],
    results: list[str],
    model: str,
) -> str:
    """
    Step 3: Synthesizer – combine specialist outputs into final response.
    """
    parts = [f"Original task: {task}\n"]
    for i, (subtask, result) in enumerate(zip(subtasks, results), 1):
        parts.append(f"Subtask {i}: {subtask}\nResult:\n{result}")

    combined = "\n\n---\n\n".join(parts)
    return await _call_model(SYNTHESIZER_SYSTEM, combined, model)


# ── Public API ────────────────────────────────────────────────────────────────

async def run_swarm(
    *,
    task: str,
    model: str,
    on_progress: Callable[[str], None] | None = None,
) -> SwarmResult:
    """
    Run the full 3-stage swarm pipeline.

    Args:
        task:        The user's task / question
        model:       Ollama model to use for all agents
        on_progress: Called with status strings throughout execution

    Returns:
        SwarmResult with subtasks, partial results, and final synthesis
    """
    if on_progress:
        on_progress("🌲 Swarm gestartet — Planer analysiert Aufgabe…")

    # Stage 1: Plan
    subtasks = await _plan(task, model)

    if on_progress:
        on_progress(
            f"📋 {len(subtasks)} Teilaufgaben erkannt:\n"
            + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(subtasks))
        )
        on_progress(f"\n⚡ {len(subtasks)} Agenten starten parallel…")

    # Stage 2: Run specialists in parallel
    specialist_coros = [
        _run_specialist(subtask, task, model, i, on_progress)
        for i, subtask in enumerate(subtasks)
    ]
    partial_results: list[str] = list(await asyncio.gather(*specialist_coros))

    if on_progress:
        on_progress("\n🔗 Synthesizer fasst Ergebnisse zusammen…")

    # Stage 3: Synthesize
    final = await _synthesize(task, subtasks, partial_results, model)

    return SwarmResult(
        task=task,
        subtasks=subtasks,
        partial_results=partial_results,
        final=final,
    )


class SwarmResult:
    """Holds the complete output of a swarm run."""

    def __init__(
        self,
        task: str,
        subtasks: list[str],
        partial_results: list[str],
        final: str,
    ) -> None:
        self.task = task
        self.subtasks = subtasks
        self.partial_results = partial_results
        self.final = final

    def __repr__(self) -> str:
        return (
            f"SwarmResult(subtasks={len(self.subtasks)}, "
            f"final_len={len(self.final)})"
        )
