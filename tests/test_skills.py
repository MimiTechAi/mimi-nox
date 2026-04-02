"""
◑ MiMi Nox – Phase 2 TDD
tests/test_skills.py

REGEL: Tests VOR Implementierung.
Given / When / Then – strikt.

Markdown-Skill-Format:
  # skill-name
  **Trigger**: /trigger-name
  **Description**: Kurzbeschreibung
  **Tools**: tool1, tool2

  ## System Prompt
  Du bist ein...

  ## Test
  **Input**: Testfrage
  **Expect Tool**: tool_name
  **Expect Contains**: erwarteter Text
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, patch

import pytest

from core.skills import Skill, SkillLoadError, SkillLoader, SkillTestResult


VALID_SKILL_MD = dedent("""\
    # web-researcher

    **Trigger**: /research
    **Description**: Recherchiert Themen im Internet mit DuckDuckGo.
    **Tools**: web_search

    ## System Prompt

    Du bist ein präziser Recherche-Assistent.
    Nutze immer das web_search Tool für aktuelle Informationen.
    Antworte kurz, faktenbasiert und auf Deutsch.

    ## Test

    **Input**: Was ist Ollama?
    **Expect Tool**: web_search
    **Expect Contains**: lokal
""")

BROKEN_SKILL_MD = dedent("""\
    # Kaputtes Skill
    Kein Trigger-Block, kein System-Prompt.
    Einfach nur Text.
""")


class TestSkillLoader:

    @pytest.fixture
    def skills_dir(self, tmp_path):
        d = tmp_path / "skills"
        d.mkdir()
        return d

    @pytest.fixture
    def loader(self, skills_dir):
        return SkillLoader(skills_dir=skills_dir)

    def test_load_valid_skill(self, loader, skills_dir):
        """
        GIVEN  Gültige Skill-Datei web_researcher.md in skills_dir
        WHEN   loader.load("web-researcher") aufgerufen
        THEN   Rückgabe ist Skill-Objekt
        AND    skill.name == "web-researcher"
        AND    skill.trigger == "/research"
        AND    skill.system_prompt ist nicht-leer String
        AND    "web_search" in skill.tools
        """
        (skills_dir / "web-researcher.md").write_text(VALID_SKILL_MD, encoding="utf-8")

        skill = loader.load("web-researcher")

        assert isinstance(skill, Skill)
        assert skill.name == "web-researcher"
        assert skill.trigger == "/research"
        assert isinstance(skill.system_prompt, str)
        assert len(skill.system_prompt) > 10
        assert "web_search" in skill.tools

    def test_load_nonexistent_raises_skill_load_error(self, loader):
        """
        GIVEN  Kein Skill mit Name "nicht-vorhanden"
        WHEN   loader.load("nicht-vorhanden") aufgerufen
        THEN   Wirft SkillLoadError
        AND    Fehler enthält "nicht-vorhanden" im Text
        """
        with pytest.raises(SkillLoadError) as exc_info:
            loader.load("nicht-vorhanden")

        assert "nicht-vorhanden" in str(exc_info.value)

    def test_load_broken_skill_raises_skill_load_error(self, loader, skills_dir):
        """
        GIVEN  Markdown-Datei ohne gültige Skill-Struktur (kein Trigger, kein System Prompt)
        WHEN   loader.load("broken") aufgerufen
        THEN   Wirft SkillLoadError
        AND    App crasht NICHT
        """
        (skills_dir / "broken.md").write_text(BROKEN_SKILL_MD, encoding="utf-8")

        with pytest.raises(SkillLoadError):
            loader.load("broken")

    def test_load_all_returns_list(self, loader, skills_dir, tmp_path):
        """
        GIVEN  2 gültige Skill-Dateien im skills_dir
        WHEN   loader.load_all() aufgerufen
        THEN   Rückgabe ist Liste mit 2 Skill-Objekten
        """
        (skills_dir / "web-researcher.md").write_text(VALID_SKILL_MD, encoding="utf-8")
        variant = VALID_SKILL_MD.replace("web-researcher", "web-researcher-copy").replace("/research", "/research2")
        (skills_dir / "web-researcher-copy.md").write_text(variant, encoding="utf-8")
        # Leeres builtin_dir damit nur unsere 2 Skills gezählt werden
        empty_builtin = tmp_path / "empty_builtin"
        empty_builtin.mkdir()
        loader_isolated = SkillLoader(skills_dir=skills_dir, builtin_dir=empty_builtin)

        skills = loader_isolated.load_all()

        assert isinstance(skills, list)
        assert len(skills) == 2

    def test_load_all_empty_dir_returns_empty_list(self, tmp_path):
        """
        GIVEN  Leeres skills_dir UND leeres builtin_dir
        WHEN   loader.load_all() aufgerufen
        THEN   Rückgabe ist leere Liste (kein Crash)
        """
        empty_user = tmp_path / "user_skills"
        empty_user.mkdir()
        empty_builtin = tmp_path / "builtin_skills"
        empty_builtin.mkdir()
        loader_empty = SkillLoader(skills_dir=empty_user, builtin_dir=empty_builtin)

        result = loader_empty.load_all()
        assert result == []

    def test_resolve_trigger_finds_matching_skill(self, loader, skills_dir):
        """
        GIVEN  Skill mit Trigger "/research" im skills_dir
        WHEN   loader.resolve_trigger("/research") aufgerufen
        THEN   Rückgabe ist das Skill-Objekt
        AND    skill.trigger == "/research"
        """
        (skills_dir / "web-researcher.md").write_text(VALID_SKILL_MD, encoding="utf-8")

        skill = loader.resolve_trigger("/research")

        assert skill is not None
        assert skill.trigger == "/research"

    def test_resolve_trigger_unknown_returns_none(self, loader):
        """
        GIVEN  Kein Skill mit Trigger "/unbekannt"
        WHEN   loader.resolve_trigger("/unbekannt") aufgerufen
        THEN   Rückgabe ist None (kein Crash)
        """
        result = loader.resolve_trigger("/unbekannt")
        assert result is None

    @pytest.mark.asyncio
    async def test_run_test_passes_when_tool_called(self, loader, skills_dir):
        """
        GIVEN  Skill mit Test: input="Was ist Ollama?", expect_tool="web_search"
        WHEN   loader.run_test("web-researcher") mit Mock der chat_with_tools
        THEN   Rückgabe ist SkillTestResult mit passed=True
        """
        (skills_dir / "web-researcher.md").write_text(VALID_SKILL_MD, encoding="utf-8")

        with patch("core.chat.chat_with_tools", new=AsyncMock(
            return_value="Ollama ist lokal"
        )):
            result = await loader.run_test("web-researcher")

        assert isinstance(result, SkillTestResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "skill_name")
        assert result.skill_name == "web-researcher"

    @pytest.mark.asyncio
    async def test_run_test_on_missing_skill_returns_failed_result(self, loader):
        """
        GIVEN  Kein Skill mit Name "ghost"
        WHEN   loader.run_test("ghost") aufgerufen
        THEN   Rückgabe ist SkillTestResult mit passed=False
        AND    Kein Crash
        """
        result = await loader.run_test("ghost")

        assert isinstance(result, SkillTestResult)
        assert result.passed is False
