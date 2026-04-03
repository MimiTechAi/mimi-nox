"""
◑ MiMi Nox – FastAPI Server
server/main.py

Startet den API-Server für die Desktop App.
Pfade für Memory/Profile/etc. werden über Env-Variablen konfiguriert
damit Tests isolierte tmp-Verzeichnisse nutzen können.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.routes import health, chat, memory, skills, profile, feedback, audio, mobile, schedule, vision
from core import __version__, __edition__, __tagline__
from core.scheduler import nox_scheduler


from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Lifecycle events: Start background warmup tasks."""
    # Warmup STT Model in background to prevent lag on first request
    def warmup_whisper():
        try:
            from core.transcribe import _get_model
            _get_model()
        except Exception:
            pass
            
    asyncio.create_task(asyncio.to_thread(warmup_whisper))

    # --- GUI Automation Safety Setup ---
    import sys
    import logging
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        
        if sys.platform == "darwin":
            logging.getLogger("uvicorn.error").warning(
                "⚡ [GUI Automation] Ensure MiMi Nox (Terminal/App) has 'Accessibility' "
                "and 'Screen Recording' permissions in macOS System Settings > Privacy & Security, "
                "otherwise vision_click tools will crash immediately."
            )
    except Exception:
        pass

    # --- Background Scheduler ---
    nox_scheduler.start()

    yield

    nox_scheduler.stop()

def create_app() -> FastAPI:
    """
    FastAPI App Factory.
    Genutzt in Tests (TestClient) und in run.py (uvicorn).
    """
    app = FastAPI(
        title=f"{__edition__} MiMi Nox API",
        description=__tagline__,
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )

    # ── CORS für Tauri WebView ─────────────────────────────────────────────
    # Tauri lädt Seiten als tauri://localhost oder http://localhost:PORT
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API Routen ─────────────────────────────────────────────────────────
    app.include_router(health.router,   prefix="/api")
    app.include_router(chat.router,     prefix="/api")
    app.include_router(memory.router,   prefix="/api")
    app.include_router(skills.router,   prefix="/api")
    app.include_router(profile.router,  prefix="/api")
    app.include_router(feedback.router, prefix="/api")
    app.include_router(audio.router,    prefix="/api")
    app.include_router(mobile.router,   prefix="/api")
    app.include_router(schedule.router, prefix="/api")
    app.include_router(vision.router,   prefix="/api")

    # ── Statische Dateien (Audio-Aufnahmen für Playback) ───────────────────
    audio_dir = Path(
        os.environ.get("MIMI_NOX_AUDIO_DIR",
                       str(Path.home() / ".mimi-nox" / "sessions" / "audio"))
    )
    audio_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

    # ── Statische Dateien (Bilder/Screenshots für Remote) ──────────────────
    image_dir = Path(
        os.environ.get("MIMI_NOX_IMAGE_DIR",
                       str(Path.home() / ".mimi-nox" / "sessions" / "images"))
    )
    image_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=str(image_dir)), name="images")

    # ── Statische Dateien (Web-Frontend) ───────────────────────────────────
    frontend_dir = Path(__file__).parent.parent / "app" / "src"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


# Standalone-Instanz (für uvicorn direkt)
app = create_app()
