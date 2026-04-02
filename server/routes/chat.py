"""server/routes/chat.py – POST /api/chat + GET /api/chat/stream (SSE)"""
from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.chat import OllamaNotReachableError, OllamaModelNotFoundError
from core.react import react_loop

router = APIRouter(tags=["Chat"])

DEFAULT_MODEL = os.environ.get("MIMI_NOX_MODEL", "phi4-mini")


# ── Pydantic Models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL
    history: list[dict] = []


class ChatResponse(BaseModel):
    response: str
    model: str


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Synchroner Chat-Endpunkt (wartet auf vollständige Antwort).
    Für einfache Anfragen und Tests.
    """
    try:
        chunks: list[str] = []
        response_text = await react_loop(
            question=request.message,
            model=request.model,
            context=request.history,
            on_chunk=chunks.append,
        )
        return ChatResponse(
            response=response_text or "".join(chunks),
            model=request.model,
        )
    except OllamaNotReachableError:
        raise HTTPException(
            status_code=503,
            detail="Ollama nicht erreichbar. Starte mit: ollama serve",
        )
    except OllamaModelNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Modell '{exc.model}' nicht installiert. Installiere mit: ollama pull {exc.model}",
        )


class StreamRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL
    history: list[dict] = []


@router.post("/chat/stream")
async def chat_stream(request: StreamRequest) -> StreamingResponse:
    """
    Streaming Chat via Server-Sent Events (SSE) — POST für lange Nachrichten.
    Jedes Token wird sofort als SSE-Event gesendet.

    Verwendung (JavaScript fetch + ReadableStream):
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message, model})
        });
        const reader = resp.body.getReader();
        // read chunks line by line
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_chunk(chunk: str) -> None:
            queue.put_nowait(chunk)

        async def run() -> None:
            try:
                await react_loop(
                    question=request.message,
                    model=request.model,
                    context=request.history,
                    on_chunk=on_chunk,
                )
            except OllamaNotReachableError:
                queue.put_nowait(json.dumps({"error": "Ollama nicht erreichbar"}))
            except OllamaModelNotFoundError as exc:
                queue.put_nowait(json.dumps({"error": f"Modell {exc.model} nicht gefunden"}))
            except Exception as exc:
                queue.put_nowait(json.dumps({"error": str(exc)}))
            finally:
                queue.put_nowait(None)  # Sentinel

        task = asyncio.create_task(run())

        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps({'chunk': item})}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
