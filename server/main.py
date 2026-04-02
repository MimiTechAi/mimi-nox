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

from server.routes import health, chat, memory, skills, profile, feedback
from core import __version__, __edition__, __tagline__


def create_app() -> FastAPI:
    """
    FastAPI App Factory.
    Genutzt in Tests (TestClient) und in run.py (uvicorn).
    """
    app = FastAPI(
        title=f"{__edition__} MiMi Nox API",
        description=__tagline__,
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )

    # ── CORS für Tauri WebView ─────────────────────────────────────────────
    # Tauri lädt Seiten als tauri://localhost oder http://localhost:PORT
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"],
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

    # ── Statische Dateien (Web-Frontend) ───────────────────────────────────
    frontend_dir = Path(__file__).parent.parent / "app" / "src"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


# Standalone-Instanz (für uvicorn direkt)
app = create_app()
