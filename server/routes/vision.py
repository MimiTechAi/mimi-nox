"""server/routes/vision.py – POST /api/vision/analyze

Nimmt ein Bild als multipart/form-data entgegen,
speichert es temporär und analysiert es mit Gemma4 E4B Vision.

Endpunkte:
  POST /api/vision/analyze   – Bild hochladen + Frage stellen
  POST /api/vision/base64    – Base64-String + Frage (für Frontend ohne Datei-Upload)
"""
from __future__ import annotations

import base64
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import ollama

router = APIRouter(tags=["Vision"])

DEFAULT_MODEL = os.environ.get("MIMI_NOX_MODEL", "gemma4:e4b")

# Erlaubte Bildformate
ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg",
    "image/webp", "image/gif", "image/bmp",
    "image/heic", "image/heif",  # iPhone Kamera-Format
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


class VisionBase64Request(BaseModel):
    image_b64: str
    question: str = "Beschreibe dieses Bild detailliert auf Deutsch."
    model: str = DEFAULT_MODEL


# ── POST /api/vision/analyze ──────────────────────────────────────────────────

@router.post("/vision/analyze")
async def analyze_uploaded_image(
    file: UploadFile = File(..., description="Bild-Datei (PNG, JPG, WEBP, GIF, BMP)"),
    question: str = Form(
        default="Beschreibe dieses Bild detailliert auf Deutsch.",
        description="Frage zum Bild",
    ),
    model: str = Form(default=DEFAULT_MODEL),
):
    """
    Bild hochladen und via Gemma4 E4B Vision analysieren.

    - Akzeptiert: PNG, JPG, WEBP, GIF, BMP (max 20 MB)
    - Gibt zurück: { analysis: str, filename: str, model: str }
    """
    # ── Validierung ───────────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstütztes Format: {content_type}. "
                   f"Erlaubt: {', '.join(sorted(ALLOWED_MIME))}",
        )

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß: {len(raw) // 1024}KB. Max: {MAX_FILE_SIZE // 1024}KB",
        )
    if len(raw) < 100:
        raise HTTPException(status_code=400, detail="Datei zu klein oder leer.")

    # ── Temporäre Datei speichern (für analyze_image Tool-Kompatibilität) ─────
    tmp_dir = Path(os.environ.get(
        "MIMI_NOX_IMAGE_DIR",
        str(Path.home() / ".mimi-nox" / "sessions" / "images")
    ))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "upload.png").suffix.lower() or ".png"
    filename = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    tmp_path = tmp_dir / filename
    tmp_path.write_bytes(raw)

    # ── Gemma4 E4B Vision aufrufen ────────────────────────────────────────────
    image_b64 = base64.b64encode(raw).decode("utf-8")

    try:
        client = ollama.AsyncClient()
        response = await client.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": question,
                    "images": [image_b64],
                }
            ],
            stream=False,
        )
        analysis = str(response.message.content or "Keine Beschreibung generiert.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vision-Fehler: {exc}")
    finally:
        # Temporäre Datei aufräumen (nach 1h über cronjob, hier sofort)
        pass  # Datei bleibt für /images/<filename> Serving verfügbar

    return {
        "analysis": analysis,
        "filename": filename,
        "image_url": f"/images/{filename}",
        "model": model,
        "question": question,
    }


# ── POST /api/vision/base64 ───────────────────────────────────────────────────

@router.post("/vision/base64")
async def analyze_base64_image(req: VisionBase64Request):
    """
    Bild als Base64-String analysieren (für Frontend das kein FormData nutzen kann).

    Body: { image_b64: "...", question: "...", model: "gemma4:e4b" }
    """
    if not req.image_b64:
        raise HTTPException(status_code=400, detail="image_b64 darf nicht leer sein.")

    # Basis-Validierung des Base64-Strings
    try:
        raw = base64.b64decode(req.image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültiger Base64-String.")

    if len(raw) < 100:
        raise HTTPException(status_code=400, detail="Bild zu klein oder leer.")

    try:
        client = ollama.AsyncClient()
        response = await client.chat(
            model=req.model,
            messages=[
                {
                    "role": "user",
                    "content": req.question,
                    "images": [req.image_b64],
                }
            ],
            stream=False,
        )
        analysis = str(response.message.content or "Keine Beschreibung generiert.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vision-Fehler: {exc}")

    return {
        "analysis": analysis,
        "model": req.model,
        "question": req.question,
    }
