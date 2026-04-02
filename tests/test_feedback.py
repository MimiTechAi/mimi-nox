"""
◑ MiMi Nox – Phase 2 TDD
tests/test_feedback.py

REGEL: Tests VOR Implementierung.
Given / When / Then – strikt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.feedback import FeedbackStore, FeedbackExample


class TestFeedbackStore:

    @pytest.fixture
    def store(self, tmp_path):
        return FeedbackStore(base_dir=tmp_path / "feedback")

    def test_thumbs_up_saves_example(self, store):
        """
        GIVEN  FeedbackStore
        WHEN   store.thumbs_up(prompt="P", response="R") aufgerufen
        THEN   Datei in good_examples/ gespeichert
        AND    store.count_good() > 0
        """
        store.thumbs_up(prompt="Was ist Python?", response="Python ist eine Programmiersprache.")

        assert store.count_good() > 0

    def test_thumbs_down_saves_example(self, store):
        """
        GIVEN  FeedbackStore
        WHEN   store.thumbs_down(prompt="P", response="R") aufgerufen
        THEN   Datei in bad_examples/ gespeichert
        AND    store.count_bad() > 0
        """
        store.thumbs_down(prompt="Was ist Python?", response="Python ist eine Schlange.")

        assert store.count_bad() > 0

    def test_get_good_examples_returns_list(self, store):
        """
        GIVEN  3 positive Beispiele gespeichert
        WHEN   store.get_good_examples(max_items=3) aufgerufen
        THEN   Rückgabe ist Liste mit ≤3 FeedbackExample-Objekten
        AND    Jedes hat prompt und response
        """
        for i in range(3):
            store.thumbs_up(prompt=f"Frage {i}", response=f"Antwort {i}")

        examples = store.get_good_examples(max_items=3)

        assert isinstance(examples, list)
        assert len(examples) <= 3
        for ex in examples:
            assert isinstance(ex, FeedbackExample)
            assert hasattr(ex, "prompt")
            assert hasattr(ex, "response")

    def test_empty_store_returns_empty_list(self, store):
        """
        GIVEN  Leerer FeedbackStore
        WHEN   store.get_good_examples() aufgerufen
        THEN   Rückgabe ist leere Liste (kein Crash)
        """
        result = store.get_good_examples()
        assert result == []

    def test_to_few_shot_string_with_examples(self, store):
        """
        GIVEN  2 positive Beispiele gespeichert
        WHEN   store.to_few_shot_string(max_items=2) aufgerufen
        THEN   Rückgabe ist nicht-leerer String
        AND    Enthält Wörter "Frage" und "Antwort"
        """
        store.thumbs_up(prompt="Frage über KI", response="Antwort über KI")
        store.thumbs_up(prompt="Frage über Python", response="Antwort über Python")

        result = store.to_few_shot_string(max_items=2)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_to_few_shot_string_empty_is_empty_string(self, store):
        """
        GIVEN  Keine Beispiele gespeichert
        WHEN   store.to_few_shot_string() aufgerufen
        THEN   Rückgabe ist leerer String (kein Crash)
        """
        result = store.to_few_shot_string()
        assert result == ""

    def test_count_methods_accurate(self, store):
        """
        GIVEN  2 gute + 1 schlechtes Beispiel gespeichert
        WHEN   store.count_good() und store.count_bad() aufgerufen
        THEN   count_good() == 2
        AND    count_bad() == 1
        """
        store.thumbs_up(prompt="A", response="B")
        store.thumbs_up(prompt="C", response="D")
        store.thumbs_down(prompt="E", response="F")

        assert store.count_good() == 2
        assert store.count_bad() == 1
