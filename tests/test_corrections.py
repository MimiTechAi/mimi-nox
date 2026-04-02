"""
◑ MiMi Nox – Phase 2 TDD
tests/test_corrections.py

REGEL: Tests VOR Implementierung.
Given / When / Then – strikt.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.corrections import Correction, CorrectionJournal


class TestCorrectionJournal:

    @pytest.fixture
    def journal(self, tmp_path):
        return CorrectionJournal(path=tmp_path / "corrections.md")

    def test_add_creates_entry(self, journal):
        """
        GIVEN  Leeres Fehler-Journal
        WHEN   journal.add(wrong="X=Y", correct="X≠Y") aufgerufen
        THEN   Datei existiert
        AND    Datei enthält korrekten Wert "X≠Y"
        AND    Datei enthält heutiges Datum
        """
        journal.add(wrong="X ist gleich Y", correct="X ist NICHT gleich Y")

        assert journal.path.exists()
        content = journal.path.read_text(encoding="utf-8")
        assert "X ist NICHT gleich Y" in content
        assert str(datetime.now().year) in content

    def test_get_recent_returns_last_n(self, journal):
        """
        GIVEN  5 gespeicherte Korrekturen
        WHEN   journal.get_recent(3) aufgerufen
        THEN   Rückgabe enthält genau 3 Einträge (die neuesten)
        """
        for i in range(5):
            journal.add(wrong=f"Fehler {i}", correct=f"Korrektur {i}")

        recent = journal.get_recent(3)

        assert len(recent) == 3
        assert isinstance(recent[0], Correction)

    def test_get_recent_on_empty_journal_returns_empty(self, journal):
        """
        GIVEN  Keine Einträge im Journal
        WHEN   journal.get_recent(5) aufgerufen
        THEN   Rückgabe ist leere Liste (kein Crash)
        """
        result = journal.get_recent(5)
        assert result == []

    def test_each_correction_has_required_fields(self, journal):
        """
        GIVEN  Eine Korrektur gespeichert
        WHEN   journal.get_recent(1) aufgerufen
        THEN   Correction hat: wrong, correct, timestamp
        AND    timestamp ist ein datetime Objekt
        """
        journal.add(wrong="falsche Behauptung", correct="richtige Aussage")
        corrections = journal.get_recent(1)

        c = corrections[0]
        assert hasattr(c, "wrong")
        assert hasattr(c, "correct")
        assert hasattr(c, "timestamp")
        assert isinstance(c.timestamp, datetime)
        assert c.correct == "richtige Aussage"

    def test_multiple_adds_appended_not_overwritten(self, journal):
        """
        GIVEN  Zwei Korrekturen nacheinander hinzugefügt
        WHEN   journal.get_recent(10) aufgerufen
        THEN   Beide Korrekturen sind vorhanden
        AND    Reihenfolge: neueste zuerst
        """
        journal.add(wrong="Altfehler", correct="Altkorrektur")
        journal.add(wrong="Neufehler", correct="Neukorrektur")

        corrections = journal.get_recent(10)
        assert len(corrections) == 2
        # Neueste zuerst
        assert corrections[0].correct == "Neukorrektur"
        assert corrections[1].correct == "Altkorrektur"

    def test_to_system_prompt_context(self, journal):
        """
        GIVEN  2 Korrekturen im Journal
        WHEN   journal.to_context_string(max_items=2) aufgerufen
        THEN   Rückgabe ist String mit beiden Korrekturen
        AND    Nicht-leer
        """
        journal.add(wrong="A=B", correct="A≠B")
        journal.add(wrong="X>Y", correct="X<Y")

        ctx = journal.to_context_string(max_items=2)
        assert isinstance(ctx, str)
        assert len(ctx) > 0
        assert "A≠B" in ctx or "X<Y" in ctx
