"""server/routes/health.py – GET /api/health"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core import __version__
from core.chat import check_ollama_connection

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    ollama: bool
    models: list[str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Prüft ob der Server und Ollama erreichbar sind.
    Gibt immer Status 200 zurück – ollama=false wenn nicht erreichbar.
    """
    connected, _, models = await check_ollama_connection(model="")
    return HealthResponse(
        status="ok",
        version=__version__,
        ollama=connected,
        models=models,
    )
