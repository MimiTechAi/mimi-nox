"""
ClawDash Chat Engine – BlackForest Edition

Async streaming wrapper around the Ollama Python client.
Designed to be called exclusively from Textual @work workers.

Pattern:
    The on_chunk callback is called for every streamed token.
    The worker (ui/app.py) uses post_message() to route chunks to the UI.
    This module knows nothing about Textual – pure async Python.

Model loading note:
    Large models (>4GB) can take 30-120s to load from disk into RAM on first
    call after Ollama restart. FIRST_CHUNK_TIMEOUT controls how long we wait
    before giving the user a "still loading…" hint.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import ollama

from core.types import Message

# How long to wait for the FIRST token before showing a "still loading" hint
FIRST_CHUNK_TIMEOUT: float = 15.0


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
