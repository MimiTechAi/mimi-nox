"""
◑ MiMi Nox – Vector Memory
core/memory.py

Speichert Konversations-Highlights mit semantischer Suche.

DESIGN: chromadb mit eingebautem default-Embedding (kein Ollama nötig).
        Die Default-Funktion nutzt lokale Sentence-Embeddings über chromadb's
        eingebauten all-MiniLM-L6-v2 (wird beim ersten Start heruntergeladen).
        Alternative: nomic-embed-text in Phase 3.

Speicherpfad: ~/.mimi-nox/memory/chroma_db/ (Standard)
              Beliebiger persist_dir für Tests.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any


DEFAULT_MEMORY_DIR = Path.home() / ".mimi-nox" / "memory" / "chroma_db"


class Memory:
    """
    Persistenter Text-Speicher mit semantischer Suche via chromadb.

    Usage:
        mem = Memory()
        mem.store("Ich bin Python-Entwickler")
        results = mem.search("Programmiersprache")
    """

    COLLECTION_NAME = "mimi_nox_memory"

    def __init__(self, persist_dir: str | None = None) -> None:
        import chromadb

        self._dir = str(persist_dir or DEFAULT_MEMORY_DIR)
        Path(self._dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=self._dir)
        # Nutze chromadb's eingebautes Default-Embedding (lokal, kein Ollama)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def store(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Speichert einen Text-Eintrag.

        Args:
            text:     Der zu speichernde Text
            metadata: Optionale Metadaten (z.B. session-id, timestamp, source)
        """
        text = text.strip()
        if not text:
            return

        doc_id = hashlib.sha256(f"{time.time()}:{text}".encode()).hexdigest()[:16]
        meta = {"timestamp": time.time(), **(metadata or {})}

        self._collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Sucht semantisch ähnliche gespeicherte Texte.

        Returns:
            Liste von dicts: [{text, metadata, score}]
            Leere Liste wenn keine Einträge vorhanden.
        """
        if self.count() == 0:
            return []

        query = query.strip()
        if not query:
            return []

        actual_k = min(top_k, self.count())
        results = self._collection.query(
            query_texts=[query],
            n_results=actual_k,
        )

        output: list[dict] = []
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            output.append({
                "text": doc,
                "metadata": meta or {},
                "score": round(max(0.0, 1.0 - float(dist)), 4),
            })

        return output

    def count(self) -> int:
        """Gibt die Anzahl gespeicherter Einträge zurück."""
        return self._collection.count()

    def clear(self) -> None:
        """Löscht alle Einträge. Nicht rückgängig machbar."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
        )
