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
    FastAPI TestClient mit isoliertem tmp_path für Memory + Profile + Skills.
    Überschreibt alle Default-Pfade via Umgebungsvariablen.
    """
    import os
    os.environ["MIMI_NOX_MEMORY_DIR"]       = str(tmp_path / "chroma_db")
    os.environ["MIMI_NOX_PROFILE_PATH"]     = str(tmp_path / "user_profile.json")
    os.environ["MIMI_NOX_CORRECTIONS_PATH"] = str(tmp_path / "corrections.md")
    os.environ["MIMI_NOX_FEEDBACK_DIR"]     = str(tmp_path)
    os.environ["MIMI_NOX_SKILLS_DIR"]       = str(tmp_path / "skills")

    # lru_cache auf Memory-Singleton zurücksetzen für Test-Isolation
    from server.routes.memory import _get_memory
    _get_memory.cache_clear()

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


# ── Skills CRUD (Phase 5) ──────────────────────────────────────────────────

class TestSkillsCRUD:
    """Skills: Erstellen, Bearbeiten, Löschen von Nutzer-Skills."""

    _SKILL_PAYLOAD = {
        "name": "mein-test-skill",
        "trigger": "/test",
        "description": "Ein Testskill für Unit-Tests.",
        "tools": ["web_search"],
        "system_prompt": "Du bist ein Test-Assistent. Antworte immer mit: TEST OK.",
    }

    def test_create_skill_returns_201(self, client):
        """
        GIVEN  Gültiges Skill-Payload
        WHEN   POST /api/skills
        THEN   Status 201
        AND    Response enthält name, trigger, description
        """
        response = client.post("/api/skills", json=self._SKILL_PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "mein-test-skill"
        assert data["trigger"] == "/test"

    def test_created_skill_appears_in_list(self, client):
        """
        GIVEN  Skill erstellt via POST /api/skills
        WHEN   GET /api/skills
        THEN   Skill ist in der Liste
        """
        client.post("/api/skills", json=self._SKILL_PAYLOAD)
        response = client.get("/api/skills")
        names = [s["name"] for s in response.json()["skills"]]
        assert "mein-test-skill" in names

    def test_created_skill_detail_accessible(self, client):
        """
        GIVEN  Skill erstellt
        WHEN   GET /api/skills/mein-test-skill
        THEN   Status 200 und system_prompt korrekt
        """
        client.post("/api/skills", json=self._SKILL_PAYLOAD)
        response = client.get("/api/skills/mein-test-skill")
        assert response.status_code == 200
        assert "TEST OK" in response.json()["system_prompt"]

    def test_update_skill_returns_200(self, client):
        """
        GIVEN  Skill existiert
        WHEN   PUT /api/skills/mein-test-skill mit neuer description
        THEN   Status 200
        AND    Neue description gespeichert
        """
        client.post("/api/skills", json=self._SKILL_PAYLOAD)
        updated = {**self._SKILL_PAYLOAD, "description": "Aktualisierte Beschreibung"}
        response = client.put("/api/skills/mein-test-skill", json=updated)
        assert response.status_code == 200

        detail = client.get("/api/skills/mein-test-skill")
        assert detail.json()["description"] == "Aktualisierte Beschreibung"

    def test_delete_user_skill_returns_200(self, client):
        """
        GIVEN  Nutzer-Skill erstellt
        WHEN   DELETE /api/skills/mein-test-skill
        THEN   Status 200
        AND    Skill nicht mehr im Listing
        """
        client.post("/api/skills", json=self._SKILL_PAYLOAD)
        response = client.delete("/api/skills/mein-test-skill")
        assert response.status_code == 200

        skills_after = client.get("/api/skills").json()["skills"]
        names = [s["name"] for s in skills_after]
        assert "mein-test-skill" not in names

    def test_delete_builtin_skill_returns_403(self, client):
        """
        GIVEN  Built-in Skill 'web-researcher'
        WHEN   DELETE /api/skills/web-researcher
        THEN   Status 403 (Builtin Skills dürfen nicht gelöscht werden)
        """
        response = client.delete("/api/skills/web-researcher")
        assert response.status_code == 403

    def test_delete_nonexistent_skill_returns_404(self, client):
        """
        GIVEN  Skill existiert nicht
        WHEN   DELETE /api/skills/phantomskill
        THEN   Status 404
        """
        response = client.delete("/api/skills/phantomskill")
        assert response.status_code == 404

    def test_create_skill_missing_fields_returns_422(self, client):
        """
        GIVEN  Payload ohne system_prompt
        WHEN   POST /api/skills
        THEN   Status 422 (Validation Error)
        """
        response = client.post("/api/skills", json={
            "name": "broken",
            "trigger": "/broken",
        })
        assert response.status_code == 422


# ── Memory CRUD (Phase 5) ─────────────────────────────────────────────────

class TestMemoryCRUD:
    """Memory: Einträge auflisten und gezielt löschen."""

    def test_memory_list_empty(self, client):
        """
        GIVEN  Leere Memory-Datenbank
        WHEN   GET /api/memory/list
        THEN   Status 200
        AND    {"entries": [], "total": 0}
        """
        response = client.get("/api/memory/list")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert data["total"] == 0

    def test_memory_list_after_store(self, client):
        """
        GIVEN  Zwei Texte gespeichert
        WHEN   GET /api/memory/list
        THEN   Beide Einträge sichtbar mit "id" Key
        """
        client.post("/api/memory/store", json={"text": "Erste Notiz"})
        client.post("/api/memory/store", json={"text": "Zweite Notiz"})
        response = client.get("/api/memory/list")
        data = response.json()
        assert data["total"] >= 2
        assert all("id" in e for e in data["entries"])

    def test_memory_delete_entry(self, client):
        """
        GIVEN  Text gespeichert + ID bekannt
        WHEN   DELETE /api/memory/{id}
        THEN   Status 200
        AND    Eintrag nicht mehr in GET /api/memory/list
        """
        client.post("/api/memory/store", json={"text": "Zu löschende Notiz"})
        entries = client.get("/api/memory/list").json()["entries"]
        assert len(entries) >= 1
        entry_id = entries[0]["id"]

        response = client.delete(f"/api/memory/{entry_id}")
        assert response.status_code == 200

        entries_after = client.get("/api/memory/list").json()["entries"]
        ids_after = [e["id"] for e in entries_after]
        assert entry_id not in ids_after

    def test_memory_delete_nonexistent_returns_404(self, client):
        """
        GIVEN  Nicht-existente ID
        WHEN   DELETE /api/memory/ghost-id-123
        THEN   Status 404
        """
        response = client.delete("/api/memory/ghost-id-123")
        assert response.status_code == 404
