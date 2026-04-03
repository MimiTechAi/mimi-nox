"""server/routes/skills.py – CRUD für Skills"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.skills import SkillLoader, SkillLoadError, BUILTIN_SKILLS_DIR

router = APIRouter(tags=["Skills"])


def _get_loader() -> SkillLoader:
    """Lädt einen SkillLoader mit ENV-konfigurierbarem Nutzer-Verzeichnis."""
    user_skills = os.environ.get("MIMI_NOX_SKILLS_DIR")
    return SkillLoader(
        skills_dir=Path(user_skills) if user_skills else None,
        builtin_dir=BUILTIN_SKILLS_DIR,
    )


# ── Pydantic Models ────────────────────────────────────────────────────────

class SkillSummary(BaseModel):
    name: str
    trigger: str
    description: str
    tools: list[str]
    is_builtin: bool = False


class SkillDetail(BaseModel):
    name: str
    trigger: str
    description: str
    tools: list[str]
    system_prompt: str
    is_builtin: bool = False


class SkillsListResponse(BaseModel):
    skills: list[SkillSummary]
    total: int


class SkillCreateRequest(BaseModel):
    name: str
    trigger: str
    description: str
    tools: list[str] = []
    system_prompt: str


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/skills", response_model=SkillsListResponse)
async def list_skills() -> SkillsListResponse:
    """Gibt alle verfügbaren Skills zurück (built-in + Nutzer)."""
    loader = _get_loader()
    skills = loader.load_all()
    summaries = [
        SkillSummary(
            name=s.name,
            trigger=s.trigger,
            description=s.description,
            tools=s.tools,
            is_builtin=loader.is_builtin(s.name),
        )
        for s in skills
    ]
    return SkillsListResponse(skills=summaries, total=len(summaries))


@router.post("/skills", response_model=SkillDetail, status_code=201)
async def create_skill(request: SkillCreateRequest) -> SkillDetail:
    """Erstellt einen neuen Nutzer-Skill."""
    loader = _get_loader()
    try:
        skill = loader.save(
            name=request.name,
            trigger=request.trigger,
            description=request.description,
            tools=request.tools,
            system_prompt=request.system_prompt,
        )
    except SkillLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SkillDetail(
        name=skill.name,
        trigger=skill.trigger,
        description=skill.description,
        tools=skill.tools,
        system_prompt=skill.system_prompt,
        is_builtin=False,
    )


@router.get("/skills/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> SkillDetail:
    """Gibt Details eines einzelnen Skills zurück."""
    loader = _get_loader()
    try:
        skill = loader.load(name)
    except SkillLoadError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' nicht gefunden.")
    return SkillDetail(
        name=skill.name,
        trigger=skill.trigger,
        description=skill.description,
        tools=skill.tools,
        system_prompt=skill.system_prompt,
        is_builtin=loader.is_builtin(name),
    )


@router.put("/skills/{name}", response_model=SkillDetail)
async def update_skill(name: str, request: SkillCreateRequest) -> SkillDetail:
    """Aktualisiert einen bestehenden Nutzer-Skill."""
    loader = _get_loader()
    if loader.is_builtin(name) and not loader.is_user_skill(name):
        raise HTTPException(
            status_code=403,
            detail=f"Built-in Skill '{name}' kann nicht direkt bearbeitet werden. Erstelle zuerst eine Kopie.",
        )
    try:
        skill = loader.save(
            name=name,
            trigger=request.trigger,
            description=request.description,
            tools=request.tools,
            system_prompt=request.system_prompt,
        )
    except SkillLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SkillDetail(
        name=skill.name,
        trigger=skill.trigger,
        description=skill.description,
        tools=skill.tools,
        system_prompt=skill.system_prompt,
        is_builtin=False,
    )


@router.delete("/skills/{name}")
async def delete_skill(name: str) -> dict:
    """Löscht einen Nutzer-Skill. Built-in Skills können nicht gelöscht werden."""
    loader = _get_loader()
    try:
        loader.delete(name)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except SkillLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"deleted": name}
