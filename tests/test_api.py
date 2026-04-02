"""
◑ MiMi Nox – Phase 4 TDD
tests/test_api.py

REGEL: Tests VOR Implementierung. ROT zuerst, dann GRÜN.
Given / When / Then – strikt.

Alle Tests nutzen FastAPI TestClient (synchron, kein echter Server).
Ollama-Calls werden vollständig gemockt.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Fixture: TestClient ────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    """
    FastAPI TestClient mit isoliertem tmp_path für Memory + Profile.
    Überschreibt die Default-Pfade via Umgebungsvariablen.
    """
    import os
    os.environ["MIMI_NOX_MEMORY_DIR"] = str(tmp_path / "chroma_db")
    os.environ["MIMI_NOX_PROFILE_PATH"] = str(tmp_path / "user_profile.json")
    os.environ["MIMI_NOX_CORRECTIONS_PATH"] = str(tmp_path / "corrections.md")
    os.environ["MIMI_NOX_FEEDBACK_DIR"] = str(tmp_path)

    from server.main import create_app
    app = create_app()
    return TestClient(app)


# ── Health ─────────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        """
        GIVEN  FastAPI Server läuft
        WHEN   GET /api/health
        THEN   Status 200
        AND    Response enthält status="ok"
        AND    Response enthält "ollama" Key (bool)
        """
        with patch("server.routes.health.check_ollama_connection", new=AsyncMock(
            return_value=(True, "OK", ["phi4-mini"])
        )):
            response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ollama" in data
        assert isinstance(data["ollama"], bool)

    def test_health_includes_version(self, client):
        """
        GIVEN  FastAPI Server läuft
        WHEN   GET /api/health
        THEN   Response enthält "version" Key (String)
        """
        with patch("server.routes.health.check_ollama_connection", new=AsyncMock(
            return_value=(False, "unreachable", [])
        )):
            response = client.get("/api/health")

        assert response.status_code == 200
        assert "version" in response.json()


# ── Chat ───────────────────────────────────────────────────────────────────

class TestChatEndpoint:

    def test_chat_returns_response(self, client):
        """
        GIVEN  FastAPI Server läuft + Ollama gemockt
        WHEN   POST /api/chat mit {"message": "Hallo", "model": "phi4-mini"}
        THEN   Status 200
        AND    Response enthält "response" Key (nicht-leerer String)
        AND    Response enthält "model" Key
        """
        with patch("server.routes.chat.react_loop", new=AsyncMock(
            return_value="Hallo! Ich bin MiMi Nox."
        )):
            response = client.post("/api/chat", json={
                "message": "Hallo",
                "model": "phi4-mini",
            })

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert "model" in data

    def test_chat_missing_message_returns_422(self, client):
        """
        GIVEN  FastAPI Server läuft
        WHEN   POST /api/chat ohne message-Feld
        THEN   Status 422 (Validation Error)
        AND    Kein Crash
        """
        response = client.post("/api/chat", json={"model": "phi4-mini"})
        assert response.status_code == 422

    def test_chat_ollama_unreachable_returns_503(self, client):
        """
        GIVEN  Ollama nicht erreichbar (OllamaNotReachableError)
        WHEN   POST /api/chat
        THEN   Status 503
        AND    Response enthält "detail" mit verständlicher Meldung
        """
        from core.chat import OllamaNotReachableError
        with patch("server.routes.chat.react_loop", new=AsyncMock(
            side_effect=OllamaNotReachableError()
        )):
            response = client.post("/api/chat", json={
                "message": "Test",
                "model": "phi4-mini",
            })

        assert response.status_code == 503
        assert "detail" in response.json()


# ── Memory ─────────────────────────────────────────────────────────────────

class TestMemoryEndpoint:

    def test_memory_search_empty_returns_empty_list(self, client):
        """
        GIVEN  Leere Memory-Datenbank (frisch initialisiert)
        WHEN   GET /api/memory/search?q=Python
        THEN   Status 200
        AND    Response: {"results": []}
        """
        response = client.get("/api/memory/search", params={"q": "Python"})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["results"] == []

    def test_memory_store_and_search(self, client):
        """
        GIVEN  Text "Python ist großartig" gespeichert
        WHEN   GET /api/memory/search?q=Python
        THEN   Status 200
        AND    results enthält mindestens 1 Eintrag
        AND    Jeder Eintrag hat "text" Key
        """
        # Store
        store_response = client.post("/api/memory/store", json={
            "text": "Python ist eine großartige Programmiersprache."
        })
        assert store_response.status_code == 200

        # Search
        search_response = client.get("/api/memory/search", params={"q": "Python"})
        assert search_response.status_code == 200
        data = search_response.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        assert "text" in data["results"][0]

    def test_memory_store_missing_text_returns_422(self, client):
        """
        GIVEN  POST /api/memory/store ohne text-Feld
        WHEN   Request gesendet
        THEN   Status 422 (Validation Error)
        """
        response = client.post("/api/memory/store", json={})
        assert response.status_code == 422


# ── Skills ─────────────────────────────────────────────────────────────────

class TestSkillsEndpoint:

    def test_skills_list_returns_skills(self, client):
        """
        GIVEN  FastAPI Server mit built-in Skills (skills/*.md)
        WHEN   GET /api/skills
        THEN   Status 200
        AND    Response enthält Liste mit ≥1 Skills
        AND    Jeder Skill hat: name, trigger, description
        """
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert len(data["skills"]) >= 1
        for skill in data["skills"]:
            assert "name" in skill
            assert "trigger" in skill
            assert "description" in skill

    def test_skill_detail_returns_skill(self, client):
        """
        GIVEN  Built-in Skill "web-researcher" vorhanden
        WHEN   GET /api/skills/web-researcher
        THEN   Status 200
        AND    Response enthält name="web-researcher"
        AND    Response enthält system_prompt (nicht-leerer String)
        """
        response = client.get("/api/skills/web-researcher")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "web-researcher"
        assert len(data["system_prompt"]) > 0

    def test_skill_not_found_returns_404(self, client):
        """
        GIVEN  Unbekannter Skill-Name
        WHEN   GET /api/skills/does-not-exist
        THEN   Status 404
        AND    Kein Crash
        """
        response = client.get("/api/skills/does-not-exist")
        assert response.status_code == 404


# ── Profile ────────────────────────────────────────────────────────────────

class TestProfileEndpoint:

    def test_get_profile_returns_default(self, client):
        """
        GIVEN  Kein Profil gespeichert (tmp_path leer)
        WHEN   GET /api/profile
        THEN   Status 200
        AND    Response enthält alle Profil-Felder
        AND    name ist null (default)
        """
        response = client.get("/api/profile")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "expertise" in data
        assert "preferred_language" in data
        assert data["name"] is None

    def test_put_profile_updates_fields(self, client):
        """
        GIVEN  Profil-Update mit name="Max", expertise="Python"
        WHEN   PUT /api/profile mit {"name": "Max", "expertise": "Python"}
        THEN   Status 200
        AND    GET /api/profile danach: name="Max", expertise="Python"
        """
        client.put("/api/profile", json={
            "name": "Max",
            "expertise": "Python",
        })
        response = client.get("/api/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Max"
        assert data["expertise"] == "Python"


# ── Feedback ───────────────────────────────────────────────────────────────

class TestFeedbackEndpoint:

    def test_thumbs_up_returns_200(self, client):
        """
        GIVEN  Prompt + Response vorhanden
        WHEN   POST /api/feedback/thumbs_up mit {"prompt": "P", "response": "R"}
        THEN   Status 200
        AND    {"saved": true}
        """
        response = client.post("/api/feedback/thumbs_up", json={
            "prompt": "Was ist Python?",
            "response": "Python ist eine Programmiersprache.",
        })
        assert response.status_code == 200
        assert response.json()["saved"] is True

    def test_thumbs_down_returns_200(self, client):
        """
        GIVEN  Prompt + Response vorhanden
        WHEN   POST /api/feedback/thumbs_down
        THEN   Status 200
        AND    {"saved": true}
        """
        response = client.post("/api/feedback/thumbs_down", json={
            "prompt": "Was ist Python?",
            "response": "Eine Schlange.",
        })
        assert response.status_code == 200
        assert response.json()["saved"] is True
