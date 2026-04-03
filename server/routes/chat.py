"""server/routes/chat.py – POST /api/chat + POST /api/chat/stream (SSE)"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.chat import OllamaNotReachableError, OllamaModelNotFoundError, OllamaModelBusyError, chat_with_tools
from core.react import reflect, react_loop
from core.commands import is_learn_command, extract_learn_topic
from core.skill_builder import build_skill
from core.skills import SkillLoadError
from core.artifact_detector import ArtifactDetector

router = APIRouter(tags=["Chat"])

DEFAULT_MODEL = os.environ.get("MIMI_NOX_MODEL", "gemma4:e4b")


# ── Pydantic Models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL
    history: list[dict] = []


class ChatResponse(BaseModel):
    response: str
    model: str


class StreamRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL
    history: list[dict] = []
    autonomous: bool = False
    images: list[str] = []  # Base64-kodierte Bilder für E4B Multimodal


class ApproveRequest(BaseModel):
    token: str
    approved: bool

# ── Globale Sandbox State ──────────────────────────────────────────────────
# Speichert Event-Schleifen für blockierende Tool-Calls
pending_sandbox: dict[str, dict] = {}


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Synchroner Chat-Endpunkt (wartet auf vollständige Antwort)."""
    try:
        response_text = await react_loop(
            question=request.message,
            model=request.model,
            context=request.history,
        )
        return ChatResponse(response=response_text or "", model=request.model)
    except OllamaNotReachableError:
        raise HTTPException(status_code=503, detail="Ollama nicht erreichbar. Starte mit: ollama serve")
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Modell '{exc.model}' nicht installiert.")


@router.post("/chat/stream")
async def chat_stream(request: StreamRequest) -> StreamingResponse:
    """
    Transparentes Streaming via SSE.

    Event-Typen (jede Zeile: data: <JSON>\n\n):
      {"type": "chunk",    "data": "..."}          → Token sofort an AI-Bubble
      {"type": "thinking", "data": "..."}          → Thinking-Token (🧠 Nox denkt)
      {"type": "activity", "cmd": "...", "status": "running|done"} → Terminal-Feed
      {"type": "reflect",  "status": "running|done", "needs_revision": bool}
      {"type": "revision", "reason": "..."}         → Bubble resetten, neue Antwort
      {"type": "error",    "msg": "..."}            → Fehleranzeige
      {"type": "done"}                              → Cursor entfernen

    Ablauf:
      1. Erste Antwort SOFORT streamen (kein Buffering → Cursor sichtbar)
      2. Reflexion → Activity-Event im Terminal
      3. Wenn needs_revision: revision-event + überarbeitete Antwort streamen
      4. done
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def emit(event: dict) -> None:
            queue.put_nowait(event)

        async def run() -> None:
            messages = list(request.history)
            # ── Bilder in User-Message einbauen (E4B Multimodal) ──────────
            user_msg: dict = {"role": "user", "content": request.message}
            if request.images:
                user_msg["images"] = request.images
            messages.append(user_msg)
            model = request.model

            _done_sent = False
            try:
                # ── /learn: Skill-Builder-Pipeline ─────────────────────────
                if is_learn_command(request.message):
                    topic = extract_learn_topic(request.message)
                    if not topic:
                        emit({"type": "chunk", "data": "💡 Nutzung: `/learn <Thema>` – z.B. `/learn Wie wir FastAPI-Routen strukturieren`"})
                        emit({"type": "done"})
                        _done_sent = True
                        return

                    emit({"type": "thinking_start"})

                    def on_learn_chunk(chunk: str) -> None:
                        emit({"type": "chunk", "data": chunk})

                    def on_learn_phase(phase: str) -> None:
                        emit({"type": "activity", "cmd": phase, "status": "running"})

                    def on_learn_tool_start(name: str, args: dict) -> None:
                        emit({"type": "activity", "cmd": f"{name}({json.dumps(args, ensure_ascii=False)[:60]})", "status": "running"})

                    def on_learn_tool_done(name: str, result: str) -> None:
                        emit({"type": "activity", "cmd": f"{name} → {result[:40]}", "status": "done"})

                    try:
                        skill = await build_skill(
                            topic=topic,
                            model=model,
                            on_phase=on_learn_phase,
                            on_chunk=on_learn_chunk,
                            on_tool_start=on_learn_tool_start,
                            on_tool_done=on_learn_tool_done,
                        )
                        # Bestätigungs-Nachricht
                        emit({"type": "chunk", "data": f"\n\n✅ **Neuer Skill erstellt:** `{skill.name}` ({skill.trigger})\n"})
                        emit({"type": "chunk", "data": f"\n_{skill.description}_"})
                        # Skill-Created Event → Frontend lädt Chips neu
                        emit({"type": "skill_created", "skill": {
                            "name": skill.name,
                            "trigger": skill.trigger,
                            "description": skill.description,
                        }})
                    except (SkillLoadError, ValueError) as exc:
                        emit({"type": "chunk", "data": f"\n\n⚠️ Skill-Erstellung fehlgeschlagen: {exc}"})

                    emit({"type": "done"})
                    _done_sent = True
                    return

                # ── Sandbox Handler ─────────────────────────────────────────
                async def _sandbox_cb(name: str, args: dict) -> bool:
                    if request.autonomous:
                        return True
                    token = str(uuid.uuid4())
                    event = asyncio.Event()
                    pending_sandbox[token] = {"event": event, "approved": False}
                    emit({"type": "sandbox_confirm", "token": token, "tool": name, "args": args})
                    await event.wait()
                    res = pending_sandbox.pop(token, {"approved": False})
                    return res["approved"]
                    
                import core.vision
                core.vision.ON_SANDBOX_CONFIRM = _sandbox_cb
                
                async def _vision_learning_cb(target: str) -> None:
                    emit({"type": "vision_learning", "target": target})
                core.vision.ON_VISION_LEARNING = _vision_learning_cb

                async def _vision_learned_success_cb(target: str) -> None:
                    emit({"type": "vision_learned_success", "target": target})
                core.vision.ON_VISION_LEARNED_SUCCESS = _vision_learned_success_cb

                # ── Phase 1: Erste Antwort sofort streamen ─────────────────
                first_chunks: list[str] = []

                def on_chunk(chunk: str) -> None:
                    first_chunks.append(chunk)
                    emit({"type": "chunk", "data": chunk})

                # Thinking-Accumulator: sammelt Wörter bis Satzende/60+ Zeichen
                _thinking_buf: list[str] = []

                def _flush_thinking_buf() -> None:
                    text = "".join(_thinking_buf).strip()
                    _thinking_buf.clear()
                    if len(text) > 5:
                        emit({"type": "activity", "cmd": f"🧠 {text[:90]}{'…' if len(text) > 90 else ''}", "status": "running"})

                def on_thinking(chunk: str) -> None:
                    emit({"type": "thinking", "data": chunk})
                    # In Buffer sammeln und bei Satzende oder 60+ Zeichen flushen
                    _thinking_buf.append(chunk)
                    buf_text = "".join(_thinking_buf)
                    # Flush bei Satzende oder genug Text
                    if len(buf_text) >= 60 or any(buf_text.rstrip().endswith(c) for c in ('.', '!', '?', '\n', '…')):
                        _flush_thinking_buf()

                def on_tool_start(name: str, args: dict) -> None:
                    emit({"type": "activity", "cmd": f"{name}({json.dumps(args, ensure_ascii=False)[:60]})", "status": "running"})

                def on_tool_done(name: str, result: str) -> None:
                    emit({"type": "activity", "cmd": f"{name} → {result[:40]}", "status": "done"})

                def on_phase(phase: str) -> None:
                    emit({"type": "activity", "cmd": phase, "status": "running"})

                # SOFORT Thinking-Event senden → User sieht was passiert
                emit({"type": "thinking_start"})

                await chat_with_tools(
                    model=model,
                    history=messages,
                    on_chunk=on_chunk,
                    on_thinking=on_thinking,
                    on_tool_start=on_tool_start,
                    on_tool_done=on_tool_done,
                    on_phase=on_phase,
                )

                # Restlichen Thinking-Buffer flushen
                _flush_thinking_buf()

                first_answer = "".join(first_chunks)

                # ── Artifact-Erkennung ─────────────────────────────────────────────
                _detector    = ArtifactDetector()
                _artifacts   = _detector.detect(first_answer)
                if _artifacts:
                    # Bubble-Text ohne Code (Placeholder stattdessen)
                    clean_text = _detector.extract_text(first_answer)
                    emit({"type": "replace_text", "text": clean_text})
                    for art in _artifacts:
                        emit({"type": "artifact", "artifact": art.to_dict()})

                # ── Phase 2: Reflexion ─────────────────────────────────────
                emit({"type": "reflect", "status": "running"})
                reflexion = await reflect(
                    response=first_answer,
                    question=request.message,
                    model=model,
                )
                emit({"type": "reflect", "status": "done", "needs_revision": reflexion.needs_revision})

                if not reflexion.needs_revision:
                    emit({"type": "done"})
                    _done_sent = True
                    return

                # ── Phase 3: Revision ──────────────────────────────────────
                emit({"type": "revision", "reason": reflexion.reason[:200]})

                messages.append({"role": "assistant", "content": first_answer})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Deine Antwort war unvollständig.\n"
                        f"Kritik: {reflexion.reason}\n\n"
                        f"Bitte gib eine verbesserte, vollständige Antwort."
                    ),
                })

                def on_chunk_rev(chunk: str) -> None:
                    emit({"type": "chunk", "data": chunk})

                await chat_with_tools(
                    model=model,
                    history=messages,
                    on_chunk=on_chunk_rev,
                    on_thinking=on_thinking,
                    on_tool_start=on_tool_start,
                    on_tool_done=on_tool_done,
                    on_phase=on_phase,
                )

            except OllamaNotReachableError:
                emit({"type": "error", "msg": "Ollama nicht erreichbar — starte: ollama serve"})
            except OllamaModelBusyError as exc:
                emit({"type": "error", "msg": f"⏳ Modell beschäftigt – bitte nochmal versuchen (Timeout nach {exc.timeout:.0f}s)"})
            except OllamaModelNotFoundError as exc:
                emit({"type": "error", "msg": f"Modell '{exc.model}' nicht installiert"})
            except Exception as exc:
                emit({"type": "error", "msg": str(exc)})
            finally:
                if not _done_sent:
                    emit({"type": "done"})
                queue.put_nowait(None)  # Sentinel

        task = asyncio.create_task(run())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            # Client hat die Verbindung abgebrochen (Senden-Button "Stopp")
            task.cancel()
            raise
        finally:
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/sandbox/approve")
async def approve_sandbox(req: ApproveRequest):
    """Nimmt Sandbox-Bestätigungen (y/n) aus dem UI entgegen."""
    if req.token in pending_sandbox:
        pending_sandbox[req.token]["approved"] = req.approved
        pending_sandbox[req.token]["event"].set()
        return {"status": "ok"}
    raise HTTPException(404, "Sandbox Token nicht gefunden oder abgelaufen")

class AutonomousRequest(BaseModel):
    enabled: bool

@router.post("/settings/autonomous")
async def set_autonomous(req: AutonomousRequest):
    """Schaltet den Autonomen Modus für GUI Fernsteuerung ein/aus."""
    os.environ["MIMI_NOX_AUTONOMOUS_MODE"] = "1" if req.enabled else "0"
    return {"status": "ok", "autonomous": req.enabled}
