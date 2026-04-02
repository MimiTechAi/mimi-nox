"""
◑ MiMi Nox – Chat Engine

Async streaming wrapper around the Ollama Python client.
Includes Tool-Calling Loop for agentic workflows.

Designed to be called exclusively from @work workers (Textual / FastAPI).
This module knows nothing about UI – pure async Python.

Tool-Calling Architecture:
    1. Non-streaming call with tools → detect tool_calls (stream=False REQUIRED)
    2. Execute each tool via core.tools.execute_tool()
    3. Stream final answer (stream=True for smooth UX)

    stream=False für Tool-Detection ist PFLICHT.
    Bekanntes Ollama-Limit: Tool-Calls brechen mit stream=True.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import ollama

from core.types import Message
from core.tools import (
    ShellConfirmationRequired,
    execute_tool,
    get_tool_schemas,
)

# How long to wait for the FIRST token before showing a "still loading" hint
FIRST_CHUNK_TIMEOUT: float = 15.0

# Maximum tool-calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS: int = 5


class OllamaNotReachableError(Exception):
    """Raised when Ollama is not running or not reachable."""

    def __init__(self) -> None:
        super().__init__(
            "Ollama is not reachable. Start it with: ollama serve"
        )


class OllamaModelNotFoundError(Exception):
    """Raised when the requested model is not available locally."""

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(
            f"Model '{model}' not found locally. Pull it with: ollama pull {model}"
        )


async def stream_response(
    *,
    model: str,
    history: list[Message],
    on_chunk: Callable[[str], None],
    on_loading_hint: Callable[[], None] | None = None,
) -> str:
    """
    Stream a response from Ollama token by token.

    Calls on_chunk(token_str) for each received token.
    If FIRST_CHUNK_TIMEOUT seconds pass before the first token arrives
    (= model is loading from disk), calls on_loading_hint() once.
    Returns the full accumulated response text when done.

    Raises:
        OllamaNotReachableError: if Ollama is not running.
        OllamaModelNotFoundError: if the model is not pulled.
        asyncio.CancelledError: propagates cleanly for Textual worker shutdown.
    """
    client = ollama.AsyncClient()
    full_response = ""
    hint_sent = False

    try:
        stream = await client.chat(
            model=model,
            messages=list(history),  # type: ignore[arg-type]
            stream=True,
        )

        async for chunk in stream:
            content: str = chunk["message"]["content"]
            if content:
                if not hint_sent and full_response == "":
                    # First real token arrived – no need for loading hint anymore
                    hint_sent = True
                full_response += content
                on_chunk(content)

        return full_response

    except asyncio.CancelledError:
        # Let the worker's cancellation propagate cleanly
        raise

    except Exception as exc:
        exc_str = str(exc).lower()

        if any(kw in exc_str for kw in ("connection", "connect", "refused", "socket")):
            raise OllamaNotReachableError() from exc

        if "not found" in exc_str or "does not exist" in exc_str:
            raise OllamaModelNotFoundError(model) from exc

        # Unknown error – re-raise for the worker to handle
        raise


async def send_message_safe(
    *,
    model: str,
    history: list[Message],
    on_chunk: Callable[[str], None],
    on_fallback: Callable[[], None] | None = None,
    on_loading_hint: Callable[[], None] | None = None,
) -> str:
    """
    Safe wrapper: tries streaming first, falls back to non-streaming on failure.

    on_loading_hint() is called if the model takes > FIRST_CHUNK_TIMEOUT seconds.
    on_fallback() is called when falling back to non-streaming mode.

    Raises OllamaNotReachableError and OllamaModelNotFoundError directly
    (these are not recoverable via fallback).
    """
    try:
        return await stream_response(
            model=model,
            history=history,
            on_chunk=on_chunk,
            on_loading_hint=on_loading_hint,
        )
    except (OllamaNotReachableError, OllamaModelNotFoundError, asyncio.CancelledError):
        raise

    except Exception:
        # Streaming failed for another reason – try non-streaming fallback
        if on_fallback is not None:
            on_fallback()

        client = ollama.AsyncClient()
        try:
            response = await client.chat(
                model=model,
                messages=list(history),  # type: ignore[arg-type]
                stream=False,
            )
            content: str = response["message"]["content"]
            on_chunk(content)
            return content

        except Exception as exc:
            exc_str = str(exc).lower()
            if any(kw in exc_str for kw in ("connection", "connect", "refused", "socket")):
                raise OllamaNotReachableError() from exc
            raise


async def list_local_models() -> list[str]:
    """
    Return list of locally available model names.
    Used for onboarding: show user what they have installed.
    Returns [] on any error.
    """
    try:
        client = ollama.AsyncClient()
        result = await asyncio.wait_for(client.list(), timeout=3.0)
        names = []
        for m in result.models:
            name = getattr(m, "model", None) or getattr(m, "name", "")
            if name:
                names.append(str(name))
        return names
    except Exception:
        return []


async def check_ollama_connection(model: str) -> tuple[bool, str, list[str]]:
    """
    Quick connectivity check. Returns (is_connected, status_message, available_models).
    Safe to call on startup without raising.

    Note: ollama 0.4+ returns pydantic models, not dicts.
    """
    try:
        client = ollama.AsyncClient()
        result = await asyncio.wait_for(client.list(), timeout=3.0)

        available_names: list[str] = []
        for m in result.models:
            name = getattr(m, "model", None) or getattr(m, "name", "")
            available_names.append(str(name))

        model_pulled = any(model in name for name in available_names)
        if model_pulled:
            return True, f"connected · {model}", available_names
        return True, f"connected · {model} (not pulled)", available_names

    except asyncio.TimeoutError:
        return False, "timeout", []
    except Exception:
        return False, "offline", []


async def chat_with_tools(
    *,
    model: str,
    history: list[Message],
    on_chunk: Callable[[str], None],
    on_tool_start: Callable[[str, dict], None] | None = None,
    on_tool_done: Callable[[str, str], None] | None = None,
    on_loading_hint: Callable[[], None] | None = None,
) -> str:
    """
    Tool-enabled chat mit automatischer Tool-Ausführung.

    Ablauf:
        1. Non-streaming Aufruf mit Tool-Schemas → Tool-Calls detektieren
        2. Tools ausführen (max MAX_TOOL_ITERATIONS Iterationen)
        3. Finale Antwort als Text via on_chunk ausgeben

    WICHTIG: stream=False für Tool-Detection ist PFLICHT.
    Bekanntes Ollama-Limit: Tool-Calls brechen mit stream=True.

    Args:
        model:          Ollama Modell-Name
        history:        Konversations-History (role/content dicts)
        on_chunk:       Callback für jeden Text-Token der finalen Antwort
        on_tool_start:  Callback wenn Tool gestartet wird (name, args)
        on_tool_done:   Callback wenn Tool fertig ist (name, result)
        on_loading_hint: Callback wenn Modell zu lange lädt

    Raises:
        OllamaNotReachableError:    Ollama nicht erreichbar
        OllamaModelNotFoundError:   Modell nicht lokal vorhanden
        ShellConfirmationRequired:  Shell-Tool braucht User-Bestätigung
    """
    client = ollama.AsyncClient()
    messages: list = list(history)
    tools = get_tool_schemas()

    # ── Schritt 1: Tool-Detection (stream=False – Pflicht!) ──────────────────
    try:
        response = await asyncio.wait_for(
            client.chat(
                model=model,
                messages=messages,
                tools=tools,
                stream=False,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise OllamaNotReachableError()
    except Exception as exc:
        exc_str = str(exc).lower()
        if any(kw in exc_str for kw in ("connection", "connect", "refused", "socket")):
            raise OllamaNotReachableError() from exc
        if "not found" in exc_str or "does not exist" in exc_str:
            raise OllamaModelNotFoundError(model) from exc
        raise

    # ── Schritt 2: Tool-Calling Loop ─────────────────────────────────────────
    iteration = 0

    while (
        hasattr(response, "message")
        and hasattr(response.message, "tool_calls")
        and response.message.tool_calls
        and iteration < MAX_TOOL_ITERATIONS
    ):
        iteration += 1

        # Assistenten-Nachricht mit tool_calls zur History hinzufügen
        messages.append(response.message)

        for tool_call in response.message.tool_calls:
            name: str = tool_call.function.name
            args: dict = tool_call.function.arguments or {}

            # Callback: Tool startet
            if on_tool_start is not None:
                on_tool_start(name, args)

            # ShellConfirmationRequired darf NOT abgefangen werden – App muss handeln
            if name == "run_shell":
                raise ShellConfirmationRequired(args.get("command", ""))

            # Tool ausführen (Fehler werden in execute_tool abgefangen)
            result = await execute_tool(name, args)

            # Callback: Tool fertig
            if on_tool_done is not None:
                on_tool_done(name, result)

            # Tool-Ergebnis zur History hinzufügen
            messages.append({
                "role": "tool",
                "content": result,
            })

        # Nächste Iteration: prüfen ob weitere Tool-Calls folgen
        try:
            response = await client.chat(
                model=model,
                messages=messages,
                tools=tools,
                stream=False,
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            if any(kw in exc_str for kw in ("connection", "connect", "refused")):
                raise OllamaNotReachableError() from exc
            raise

    # Max Iterationen aufgebraucht?
    if iteration >= MAX_TOOL_ITERATIONS:
        warning = f"[⚠ Maximale Tool-Iterationen ({MAX_TOOL_ITERATIONS}) erreicht]"
        on_chunk(warning)
        return warning

    # ── Schritt 3: Finale Antwort ausgeben ───────────────────────────────────
    final_content: str = ""

    if hasattr(response, "message") and response.message.content:
        final_content = str(response.message.content)
        # Wort-für-Wort ausgeben für smooth streaming Effekt
        words = final_content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            on_chunk(chunk)
            await asyncio.sleep(0.008)  # smooth streaming feel

    return final_content

