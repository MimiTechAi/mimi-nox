"""
◑ MiMi Nox – Background Job Scheduler
core/scheduler.py

APScheduler-Integration für asynchrone Hintergrund-Jobs.
Nutze /schedule im Chat, um wiederkehrende Aufgaben zu definieren.
"""
from __future__ import annotations

import asyncio
import json
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Persistente Job-Liste
_JOBS_FILE = Path.home() / ".mimi-nox" / "scheduled_jobs.json"

# Registry für Live-Results (in-memory, pro Server-Session)
_job_results: list[dict] = []


class NoxScheduler:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._on_result_callback: Callable[[dict], None] | None = None

    def start(self):
        self._scheduler.start()
        self._load_persisted_jobs()
        logger.info("◑ NoxScheduler gestartet.")

    def stop(self):
        self._scheduler.shutdown(wait=False)

    def set_result_callback(self, cb: Callable[[dict], None]):
        """Callback, den das SSE-Streaming bei neuen Job-Ergebnissen aufruft."""
        self._on_result_callback = cb

    def list_jobs(self) -> list[dict]:
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return jobs

    def remove_job(self, job_id: str) -> bool:
        try:
            self._scheduler.remove_job(job_id)
            self._persist_jobs()
            return True
        except Exception:
            return False

    def add_job(self, task_description: str, cron_expr: str, job_id: str | None = None) -> str:
        """
        Fügt einen neuen Cron-Job hinzu.

        Args:
            task_description: Was MiMi bei jedem Auslösen tun soll (natürliche Sprache).
            cron_expr:        Cron-String: "minute hour day_of_month month day_of_week"
                              Beispiel: "0 8 * * *" = täglich 8 Uhr
            job_id:           Optional. Wird automatisch generiert falls leer.
        Returns:
            Die job_id des erstellten Jobs.
        """
        import uuid
        if not job_id:
            job_id = f"nox_job_{uuid.uuid4().hex[:8]}"

        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Ungültiger Cron-Ausdruck: '{cron_expr}'. Erwartet: 'min hour dom month dow'")

        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone="Europe/Berlin",
        )

        self._scheduler.add_job(
            func=self._run_task,
            trigger=trigger,
            id=job_id,
            name=task_description[:80],
            args=[task_description, job_id],
            replace_existing=True,
            misfire_grace_time=3600,  # 1 Stunde Toleranz falls Server kurz offline
        )

        self._persist_jobs()
        logger.info(f"◑ Job '{job_id}' geplant: '{task_description}' @ cron({cron_expr})")
        return job_id

    async def _run_task(self, task_description: str, job_id: str):
        """Führt eine geplante Aufgabe aus und speichert das Ergebnis."""
        from core.react import react_loop  # lazy import to avoid circular

        logger.info(f"◑ Job '{job_id}' wird ausgeführt: {task_description[:60]}…")
        start_ts = datetime.now(timezone.utc).isoformat()
        result = ""
        error = None

        try:
            result = await react_loop(
                question=task_description,
                model=None,  # uses default
                context=[],
            )
        except Exception as exc:
            error = str(exc)
            logger.error(f"◑ Job '{job_id}' fehlgeschlagen: {exc}")

        entry = {
            "job_id": job_id,
            "task": task_description,
            "executed_at": start_ts,
            "result": result or "",
            "error": error,
        }
        _job_results.append(entry)

        # Trim to last 50 entries
        if len(_job_results) > 50:
            _job_results.pop(0)

        # Notify SSE bridge if connected
        if self._on_result_callback:
            try:
                self._on_result_callback(entry)
            except Exception:
                pass

    def get_results(self, limit: int = 20) -> list[dict]:
        return list(reversed(_job_results[-limit:]))

    # ── Persistence ────────────────────────────────────────────────────────
    def _persist_jobs(self):
        _JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        jobs_data = []
        for job in self._scheduler.get_jobs():
            trigger = job.trigger
            if isinstance(trigger, CronTrigger):
                fields = {f.name: str(f) for f in trigger.fields}
                cron_str = (
                    f"{fields.get('minute','*')} "
                    f"{fields.get('hour','*')} "
                    f"{fields.get('day','*')} "
                    f"{fields.get('month','*')} "
                    f"{fields.get('day_of_week','*')}"
                )
                jobs_data.append({
                    "id": job.id,
                    "name": job.name,
                    "cron": cron_str,
                })
        _JOBS_FILE.write_text(json.dumps(jobs_data, indent=2, ensure_ascii=False))

    def _load_persisted_jobs(self):
        if not _JOBS_FILE.exists():
            return
        try:
            jobs_data = json.loads(_JOBS_FILE.read_text())
            for jd in jobs_data:
                self.add_job(
                    task_description=jd["name"],
                    cron_expr=jd["cron"],
                    job_id=jd["id"],
                )
            logger.info(f"◑ {len(jobs_data)} persistierte Jobs wiederhergestellt.")
        except Exception as exc:
            logger.warning(f"◑ Persisted Jobs konnten nicht geladen werden: {exc}")


# Singleton
nox_scheduler = NoxScheduler()
