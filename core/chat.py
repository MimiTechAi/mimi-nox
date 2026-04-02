"""
ClawDash Chat Engine – BlackForest Edition

Async streaming wrapper around the Ollama Python client.
Designed to be called exclusively from Textual @work workers.

Pattern:
    The on_chunk callback is called for every streamed token.
    The worker (ui/app.py) uses post_message() to route chunks to the UI.
    This module knows nothing about Textual – pure async Python.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import ollama

from core.types import Message


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
) -> str:
    """
    Stream a response from Ollama token by token.

    Calls on_chunk(token_str) for each received token.
    Returns the full accumulated response text when done.

    Raises:
        OllamaNotReachableError: if Ollama is not running.
        OllamaModelNotFoundError: if the model is not pulled.
        asyncio.CancelledError: if the Textual worker is cancelled – let it propagate.
    """
    client = ollama.AsyncClient()
    full_response = ""

    try:
        stream = await client.chat(
            model=model,
            messages=list(history),  # type: ignore[arg-type]
            stream=True,
        )
        async for chunk in stream:
            # asyncio.CancelledError will propagate naturally from here
            content: str = chunk["message"]["content"]
            if content:
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
) -> str:
    """
    Safe wrapper: tries streaming first, falls back to non-streaming on failure.

    on_fallback() is called when falling back, so the UI can show a hint.

    Raises OllamaNotReachableError and OllamaModelNotFoundError directly
    (these are not recoverable via fallback).
    """
    try:
        return await stream_response(
            model=model,
            history=history,
            on_chunk=on_chunk,
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


async def check_ollama_connection(model: str) -> tuple[bool, str]:
    """
    Quick connectivity check. Returns (is_connected, status_message).
    Safe to call on startup without raising.
    
    Note: ollama 0.4+ returns pydantic models, not dicts.
    We use attribute access (result.models, m.model) accordingly.
    """
    try:
        client = ollama.AsyncClient()
        result = await asyncio.wait_for(client.list(), timeout=3.0)
        # result is a ListResponse pydantic model
        # Each entry has a .model attribute (full name like 'llama3.2:latest')
        available_names = []
        for m in result.models:
            name = getattr(m, "model", None) or getattr(m, "name", "")
            available_names.append(str(name))
        
        model_pulled = any(model in name for name in available_names)
        if model_pulled:
            return True, f"connected · {model}"
        return True, f"connected · {model} (not pulled – run: ollama pull {model})"
    except asyncio.TimeoutError:
        return False, "timeout"
    except Exception:
        return False, "offline"
