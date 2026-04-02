"""
◑ MiMi Nox – Phase 2 TDD
tests/test_memory.py

REGEL: Tests VOR Implementierung geschrieben.
Alle Tests müssen ROT sein bis core/memory.py vollständig ist.

Given / When / Then – strikt.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.memory import Memory


class TestMemoryStore:

    @pytest.fixture
    def mem(self, tmp_path):
        """Frische Memory-Instanz für jeden Test."""
        return Memory(persist_dir=str(tmp_path / "chroma_test"))

    def test_store_creates_no_exception(self, mem):
        """
        GIVEN  Leere Memory-Instanz
        WHEN   mem.store("Ich bin Python-Entwickler") aufgerufen
        THEN   Keine Exception
        AND    mem.count() > 0
        """
        mem.store("Ich bin Python-Entwickler", metadata={"source": "test"})
        assert mem.count() > 0

    def test_search_returns_relevant_result(self, mem):
        """
        GIVEN  Gespeicherter Text: "Ich bin Python-Entwickler und mag asyncio"
        WHEN   mem.search("Programmiersprache Python") aufgerufen
        THEN   Rückgabe ist Liste mit ≥1 Einträgen
        AND    top-Ergebnis enthält "Python"
        """
        mem.store("Ich bin Python-Entwickler und mag asyncio")
        results = mem.search("Programmiersprache Python", top_k=3)

        assert isinstance(results, list)
        assert len(results) >= 1
        assert any("Python" in r["text"] for r in results)

    def test_search_on_empty_db_returns_empty_list(self, mem):
        """
        GIVEN  Leere Memory-Datenbank
        WHEN   mem.search("irgendwas") aufgerufen
        THEN   Rückgabe ist leere Liste (kein Crash)
        """
        results = mem.search("irgendwas")
        assert results == []

    def test_clear_removes_all_entries(self, mem):
        """
        GIVEN  Mehrere gespeicherte Einträge
        WHEN   mem.clear() aufgerufen, dann mem.search()
        THEN   Rückgabe ist leere Liste
        AND    mem.count() == 0
        """
        mem.store("Eintrag 1")
        mem.store("Eintrag 2")
        assert mem.count() > 0

        mem.clear()

        assert mem.count() == 0
        assert mem.search("Eintrag") == []

    def test_store_multiple_entries(self, mem):
        """
        GIVEN  3 verschiedene Texte werden gespeichert
        WHEN   mem.count() aufgerufen
        THEN   Rückgabe ist 3
        """
        mem.store("Python ist eine Programmiersprache")
        mem.store("Rust ist schnell und sicher")
        mem.store("JavaScript läuft im Browser")

        assert mem.count() == 3

    def test_search_returns_at_most_top_k(self, mem):
        """
        GIVEN  5 ähnliche Einträge gespeichert
        WHEN   mem.search(query, top_k=2) aufgerufen
        THEN   Rückgabe enthält ≤2 Einträge
        """
        for i in range(5):
            mem.store(f"Eintrag Nummer {i} über Python und KI")

        results = mem.search("Python KI", top_k=2)
        assert len(results) <= 2

    def test_each_result_has_required_keys(self, mem):
        """
        GIVEN  Gespeicherter Eintrag mit text und metadata
        WHEN   mem.search() aufgerufen
        THEN   Jedes Ergebnis hat keys: text, metadata, score
        """
        mem.store("Test-Eintrag", metadata={"session": "abc"})
        results = mem.search("Test", top_k=1)

        assert len(results) >= 1
        for r in results:
            assert "text" in r
            assert "metadata" in r
            assert "score" in r
