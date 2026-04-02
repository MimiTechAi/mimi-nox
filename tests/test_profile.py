"""
◑ MiMi Nox – Phase 2 TDD
tests/test_profile.py

REGEL: Tests VOR Implementierung.
Given / When / Then – strikt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.profile import UserProfile, load_profile, save_profile, update_profile


class TestUserProfile:

    @pytest.fixture
    def profile_path(self, tmp_path):
        return tmp_path / "user_profile.json"

    def test_load_returns_default_when_no_file(self, profile_path):
        """
        GIVEN  Keine Profil-Datei vorhanden
        WHEN   load_profile(path) aufgerufen
        THEN   Rückgabe ist UserProfile mit None-Defaults
        AND    Kein Crash
        """
        profile = load_profile(path=profile_path)

        assert isinstance(profile, UserProfile)
        assert profile.name is None
        assert profile.expertise is None
        assert profile.preferred_language is None
        assert isinstance(profile.topics_of_interest, list)

    def test_save_and_load_roundtrip(self, profile_path):
        """
        GIVEN  UserProfile mit name="Max", expertise="Python"
        WHEN   save_profile() und dann load_profile() aufgerufen
        THEN   Geladenes Profil hat name="Max", expertise="Python"
        AND    Alle gespeicherten Felder werden wiederhergestellt
        """
        profile = UserProfile(
            name="Max",
            expertise="Python-Entwickler",
            preferred_language="Deutsch",
            response_style="kurz und direkt",
            topics_of_interest=["KI", "Python", "Datenschutz"],
        )
        save_profile(profile, path=profile_path)
        loaded = load_profile(path=profile_path)

        assert loaded.name == "Max"
        assert loaded.expertise == "Python-Entwickler"
        assert loaded.preferred_language == "Deutsch"
        assert loaded.response_style == "kurz und direkt"
        assert "KI" in loaded.topics_of_interest

    def test_update_changes_only_specified_fields(self, profile_path):
        """
        GIVEN  Gespeichertes Profil mit name="Max", expertise="Python"
        WHEN   update_profile(preferred_style="ausführlich") aufgerufen
        THEN   name und expertise unverändert
        AND    preferred_language="ausführlich"
        """
        profile = UserProfile(name="Max", expertise="Python")
        save_profile(profile, path=profile_path)

        update_profile({"response_style": "ausführlich"}, path=profile_path)
        loaded = load_profile(path=profile_path)

        assert loaded.name == "Max"
        assert loaded.expertise == "Python"
        assert loaded.response_style == "ausführlich"

    def test_load_handles_corrupt_json_gracefully(self, profile_path):
        """
        GIVEN  Korrupte JSON-Datei im Profil-Pfad
        WHEN   load_profile(path) aufgerufen
        THEN   Kein Crash
        AND    Rückgabe ist default UserProfile
        """
        profile_path.write_text("{ dieser json ist kaputt !!!", encoding="utf-8")
        profile = load_profile(path=profile_path)

        assert isinstance(profile, UserProfile)
        assert profile.name is None

    def test_save_creates_parent_directory(self, tmp_path):
        """
        GIVEN  Profil-Pfad in nicht-existierendem Verzeichnis
        WHEN   save_profile() aufgerufen
        THEN   Verzeichnis wird erstellt
        AND    Datei wird geschrieben
        """
        deep_path = tmp_path / "deep" / "nested" / "profile.json"
        profile = UserProfile(name="Test")
        save_profile(profile, path=deep_path)

        assert deep_path.exists()
        assert json.loads(deep_path.read_text())["name"] == "Test"

    def test_profile_to_context_string(self, profile_path):
        """
        GIVEN  UserProfile mit mehreren Feldern
        WHEN   profile.to_context_string() aufgerufen
        THEN   Rückgabe ist nicht-leerer String
        AND    Enthält den Namen des Users
        """
        profile = UserProfile(
            name="Anna",
            expertise="Grafikdesignerin",
            preferred_language="Deutsch",
        )
        ctx = profile.to_context_string()

        assert isinstance(ctx, str)
        assert "Anna" in ctx
