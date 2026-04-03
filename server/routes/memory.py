"""server/routes/memory.py – GET /api/memory/search + POST /api/memory/store"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.memory import Memory

router = APIRouter(tags=["Memory"])


@lru_cache(maxsize=1)
def _get_memory() -> Memory:
    """Liefert Memory-Singleton mit konfiguriertem Pfad (testbar via ENV)."""
    path = os.environ.get("MIMI_NOX_MEMORY_DIR")
    return Memory(persist_dir=path) if path else Memory()


# ── Pydantic Models ────────────────────────────────────────────────────────

class MemoryStoreRequest(BaseModel):
    text: str
    metadata: dict = {}


class MemoryResult(BaseModel):
    text: str
    score: float
    metadata: dict = {}


class MemoryEntry(BaseModel):
    id: str
    text: str
    metadata: dict = {}


class MemoryListResponse(BaseModel):
    entries: list[MemoryEntry]
    total: int


class MemorySearchResponse(BaseModel):
    results: list[MemoryResult]
    query: str


class MemoryStoreResponse(BaseModel):
    stored: bool


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/memory/list", response_model=MemoryListResponse)
async def memory_list(limit: int = 100) -> MemoryListResponse:
    """Listet alle Memory-Einträge mit IDs (neueste zuerst)."""
    memory = _get_memory()
    raw = memory.list_all(limit=limit)
    entries = [MemoryEntry(id=e["id"], text=e["text"], metadata=e.get("metadata", {})) for e in raw]
    return MemoryListResponse(entries=entries, total=len(entries))


@router.delete("/memory/{doc_id}")
async def memory_delete(doc_id: str) -> dict:
    """Löscht einen einzelnen Memory-Eintrag per ID."""
    memory = _get_memory()
    try:
        memory.delete(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Memory-Eintrag '{doc_id}' nicht gefunden.")
    return {"deleted": doc_id}


@router.get("/memory/search", response_model=MemorySearchResponse)
async def memory_search(q: str, top_k: int = 5) -> MemorySearchResponse:
    """
    Semantische Suche im persistenten Memory.
    Gibt leere Liste zurück wenn DB leer oder kein Match.
    """
    memory = _get_memory()
    raw = memory.search(query=q, top_k=top_k)
    results = [
        MemoryResult(
            text=r["text"],
            score=r["score"],
            metadata=r.get("metadata", {}),
        )
        for r in raw
    ]
    return MemorySearchResponse(results=results, query=q)


@router.post("/memory/store", response_model=MemoryStoreResponse)
async def memory_store(request: MemoryStoreRequest) -> MemoryStoreResponse:
    """Speichert einen Text im persistenten Memory."""
    memory = _get_memory()
    memory.store(text=request.text, metadata=request.metadata)
    return MemoryStoreResponse(stored=True)
