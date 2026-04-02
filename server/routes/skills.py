"""server/routes/skills.py – GET /api/skills + GET /api/skills/{name}"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.skills import SkillLoader, SkillLoadError

router = APIRouter(tags=["Skills"])

_loader = SkillLoader()


# ── Pydantic Models ────────────────────────────────────────────────────────

class SkillSummary(BaseModel):
    name: str
    trigger: str
    description: str
    tools: list[str]


class SkillDetail(BaseModel):
    name: str
    trigger: str
    description: str
    tools: list[str]
    system_prompt: str


class SkillsListResponse(BaseModel):
    skills: list[SkillSummary]
    total: int


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/skills", response_model=SkillsListResponse)
async def list_skills() -> SkillsListResponse:
    """Gibt alle verfügbaren Skills zurück (built-in + User)."""
    skills = _loader.load_all()
    summaries = [
        SkillSummary(
            name=s.name,
            trigger=s.trigger,
            description=s.description,
            tools=s.tools,
        )
        for s in skills
    ]
    return SkillsListResponse(skills=summaries, total=len(summaries))


@router.get("/skills/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> SkillDetail:
    """
    Gibt Details eines einzelnen Skills zurück.
    Wirft 404 wenn Skill nicht gefunden.
    """
    try:
        skill = _loader.load(name)
    except SkillLoadError:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' nicht gefunden.")
    return SkillDetail(
        name=skill.name,
        trigger=skill.trigger,
        description=skill.description,
        tools=skill.tools,
        system_prompt=skill.system_prompt,
    )
