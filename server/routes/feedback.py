"""server/routes/feedback.py – POST /api/feedback/thumbs_up + thumbs_down"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.feedback import FeedbackStore

router = APIRouter(tags=["Feedback"])


def _get_store() -> FeedbackStore:
    """FeedbackStore mit konfiguriertem Basispfad (testbar via ENV)."""
    base = os.environ.get("MIMI_NOX_FEEDBACK_DIR")
    return FeedbackStore(base_dir=Path(base)) if base else FeedbackStore()


# ── Pydantic Models ────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    prompt: str
    response: str


class FeedbackResponse(BaseModel):
    saved: bool


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/feedback/thumbs_up", response_model=FeedbackResponse)
async def thumbs_up(request: FeedbackRequest) -> FeedbackResponse:
    """Speichert ein positives Feedback-Beispiel (👍)."""
    store = _get_store()
    store.thumbs_up(prompt=request.prompt, response=request.response)
    return FeedbackResponse(saved=True)


@router.post("/feedback/thumbs_down", response_model=FeedbackResponse)
async def thumbs_down(request: FeedbackRequest) -> FeedbackResponse:
    """Speichert ein negatives Feedback-Beispiel (👎)."""
    store = _get_store()
    store.thumbs_down(prompt=request.prompt, response=request.response)
    return FeedbackResponse(saved=True)
