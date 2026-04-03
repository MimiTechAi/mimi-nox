"""
◑ MiMi Nox – Audio-Route
server/routes/audio.py

POST /api/audio/transcribe → Upload + lokale STT-Transkription.

Sicherheit:
  - Dateigröße ≤ 15 MB
  - MIME-Type Whitelist
  - Path-Sandboxing (nur in ~/.mimi-nox/sessions/audio/)
  - Dateiname: {timestamp}_{uuid}.{ext} (kein User-Input)

MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

router = APIRouter(tags=["Audio"])

# ── Konfiguration ──────────────────────────────────────────────────────────

MAX_AUDIO_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "video/webm",  # Chrome sendet manchmal video/webm für reines Audio
}

# Extension-Mapping
CONTENT_TYPE_EXT = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
}


def _get_audio_dir() -> Path:
    """Audio-Verzeichnis aus Env-Variable (für Test-Isolation)."""
    return Path(
        os.environ.get("MIMI_NOX_AUDIO_DIR",
                       str(Path.home() / ".mimi-nox" / "sessions" / "audio"))
    )


# ── Response Models ────────────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    text: str
    audio_url: str
    duration_hint: str


# ── Route ──────────────────────────────────────────────────────────────────

@router.post("/audio/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio-Datei (webm, mp4, wav, m4a)"),
):
    """
    Empfängt Audio vom Frontend, speichert es sicher und transkribiert lokal.

    Returns:
        text: Transkribierter Text
        audio_url: Pfad zum Abspielen im Frontend
        duration_hint: "Sprachnachricht" oder "Stille erkannt"
    """
    # ── 1. MIME-Type validieren ─────────────────────────────────────────
    # Codec-Parameter abschneiden: "audio/webm;codecs=opus" → "audio/webm"
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Ungültiger Audio-Typ: '{content_type}'. "
                   f"Erlaubt: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    # ── 2. Datei lesen + Größe prüfen ──────────────────────────────────
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Audio zu groß ({len(audio_bytes) // 1024 // 1024} MB). "
                   f"Maximum: {MAX_AUDIO_SIZE // 1024 // 1024} MB.",
        )

    if len(audio_bytes) == 0:
        raise HTTPException(status_code=422, detail="Leere Audio-Datei.")

    # ── 3. Sicher speichern (kein User-Input im Pfad!) ─────────────────
    audio_dir = _get_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)

    ext = CONTENT_TYPE_EXT.get(content_type, ".webm")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{timestamp}_{unique_id}{ext}"

    # Path-Traversal-Schutz
    target = (audio_dir / filename).resolve()
    if not str(target).startswith(str(audio_dir.resolve())):
        raise HTTPException(status_code=400, detail="Ungültiger Dateipfad.")

    target.write_bytes(audio_bytes)

    # ── 4. Transkribieren ──────────────────────────────────────────────
    try:
        from core.transcribe import transcribe, is_whisper_available

        if not is_whisper_available():
            # Fallback: Datei gespeichert, aber keine Transkription möglich
            return TranscribeResponse(
                text="[Sprachnachricht – Transkription nicht verfügbar. "
                     "Installiere: pip install faster-whisper]",
                audio_url=f"/audio/{filename}",
                duration_hint="Sprachnachricht",
            )

        text = await transcribe(target)

        if not text:
            return TranscribeResponse(
                text="",
                audio_url=f"/audio/{filename}",
                duration_hint="Stille erkannt",
            )

        return TranscribeResponse(
            text=text,
            audio_url=f"/audio/{filename}",
            duration_hint="Sprachnachricht",
        )

    except Exception as exc:
        # Datei ist gespeichert, aber Transkription schlug fehl
        return TranscribeResponse(
            text=f"[Transkriptions-Fehler: {exc}]",
            audio_url=f"/audio/{filename}",
            duration_hint="Fehler",
        )

# ── Sprachsynthese (Edge-TTS) ─────────────────────────────────────────────

import edge_tts

class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "de-DE-KillianNeural"

class SynthesizeResponse(BaseModel):
    audio_url: str

@router.post("/audio/synthesize", response_model=SynthesizeResponse)
async def synthesize_audio(req: SynthesizeRequest):
    """
    Konvertiert Text über Microsoft Edge-TTS in lebensechte Neural Streams.
    Liefert die URL zur lokal gespeicherten MP3.
    """
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text ist leer")
        
    audio_dir = _get_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp3"
    target = audio_dir / filename
    
    try:
        communicate = edge_tts.Communicate(text, req.voice)
        await communicate.save(str(target))
        return SynthesizeResponse(audio_url=f"/audio/{filename}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS Fehler: {exc}")
