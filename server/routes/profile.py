"""server/routes/profile.py – GET /api/profile + PUT /api/profile"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.profile import UserProfile, load_profile, save_profile

router = APIRouter(tags=["Profile"])


def _profile_path() -> Path | None:
    """Gibt konfigurierten Profilpfad zurück (ENV oder None → Default)."""
    p = os.environ.get("MIMI_NOX_PROFILE_PATH")
    return Path(p) if p else None


# ── Pydantic Models ────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    name: str | None
    expertise: str | None
    preferred_language: str | None
    response_style: str | None
    topics_of_interest: list[str]
    projects: list[str]
    dislikes: list[str]


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    expertise: str | None = None
    preferred_language: str | None = None
    response_style: str | None = None
    topics_of_interest: list[str] | None = None
    projects: list[str] | None = None
    dislikes: list[str] | None = None


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse)
async def get_profile() -> ProfileResponse:
    """Gibt das aktuelle Nutzerprofil zurück."""
    profile = load_profile(path=_profile_path())
    return ProfileResponse(
        name=profile.name,
        expertise=profile.expertise,
        preferred_language=profile.preferred_language,
        response_style=profile.response_style,
        topics_of_interest=profile.topics_of_interest,
        projects=profile.projects,
        dislikes=profile.dislikes,
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(request: ProfileUpdateRequest) -> ProfileResponse:
    """
    Aktualisiert einzelne Felder des Nutzerprofils.
    Nur gesetzte Felder werden überschrieben.
    """
    path = _profile_path()
    profile = load_profile(path=path)

    # Nur explizit gesetzte Felder updaten
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    for key, value in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    save_profile(profile, path=path)

    return ProfileResponse(
        name=profile.name,
        expertise=profile.expertise,
        preferred_language=profile.preferred_language,
        response_style=profile.response_style,
        topics_of_interest=profile.topics_of_interest,
        projects=profile.projects,
        dislikes=profile.dislikes,
    )
