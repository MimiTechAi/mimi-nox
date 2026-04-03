"""
◑ MiMi Nox – Scheduler REST API
server/routes/schedule.py

Endpoints:
  POST /api/schedule          → Job anlegen
  GET  /api/schedule          → Alle Jobs auflisten
  DELETE /api/schedule/{id}   → Job entfernen
  GET  /api/schedule/results  → Letzte Job-Ergebnisse
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.scheduler import nox_scheduler

router = APIRouter(tags=["Schedule"])


class ScheduleCreateRequest(BaseModel):
    task: str          # Aufgaben-Beschreibung in natürlicher Sprache
    cron: str          # "0 8 * * *" = täglich 8 Uhr


class ScheduleCreateResponse(BaseModel):
    job_id: str
    message: str


@router.post("/schedule", response_model=ScheduleCreateResponse)
def create_schedule(req: ScheduleCreateRequest) -> ScheduleCreateResponse:
    """Legt einen neuen wiederkehrenden Hintergrund-Job an."""
    try:
        job_id = nox_scheduler.add_job(
            task_description=req.task,
            cron_expr=req.cron,
        )
        return ScheduleCreateResponse(
            job_id=job_id,
            message=f"Job '{job_id}' geplant. Nächster Lauf: {_next_run(job_id)}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/schedule")
def list_schedules():
    """Gibt alle aktiven Jobs zurück."""
    return {"jobs": nox_scheduler.list_jobs()}


@router.get("/schedule/results")
def get_results(limit: int = 20):
    """Gibt die letzten N Job-Ergebnisse zurück (neueste zuerst)."""
    return {"results": nox_scheduler.get_results(limit=limit)}


@router.delete("/schedule/{job_id}")
def delete_schedule(job_id: str):
    """Löscht einen Job per ID."""
    removed = nox_scheduler.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' nicht gefunden.")
    return {"status": "deleted", "job_id": job_id}


# ── Helper ─────────────────────────────────────────────────────────────────

def _next_run(job_id: str) -> str:
    for j in nox_scheduler.list_jobs():
        if j["id"] == job_id:
            return j["next_run"] or "unbekannt"
    return "unbekannt"
