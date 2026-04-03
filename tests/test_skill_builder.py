"""
◑ MiMi Nox – Skill Builder Tests
tests/test_skill_builder.py

TDD Tests für den /learn Skill-Builder.
When/Given/Then Spezifikationen.

Getestet: XML-Extraktion, Path-Traversal-Schutz, Überschreib-Schutz,
          build_skill Integration, Command-Detection.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.skill_builder import (
    build_skill,
    extract_skill_content,
    extract_skill_markdown,  # Legacy-Alias
    extract_skill_name,
    extract_skill_filename,
    _validate_skill_path,
    _unique_skill_name,
    MAX_SCAN_FILES,
)
from core.skills import SkillLoader, SkillLoadError
from core.commands import (
    is_learn_command,
    extract_learn_topic,
    is_command,
    get_completions,
)


# ---------------------------------------------------------------------------
# extract_skill_content Tests (XML-Extraktion)
# ---------------------------------------------------------------------------

class TestExtractSkillContent:
    """Parser für LLM-Output → Skill-Markdown via XML-Tags."""

    def test_GIVEN_xml_tags_WHEN_extracted_THEN_returns_content(self):
        """
        GIVEN  LLM-Output mit <new_skill_content>-Tags
        WHEN   extract_skill_content() aufgerufen wird
        THEN   Nur der Inhalt zwischen den Tags wird zurückgegeben
        """
        llm_output = (
            "Hier ist dein neuer Skill:\n\n"
            "<skill_filename>test-skill.md</skill_filename>\n"
            "<new_skill_content>\n"
            "# test-skill\n\n"
            "**Trigger**: /test\n"
            "**Description**: Ein Test-Skill.\n"
            "**Tools**: web_search\n\n"
            "## System Prompt\n\n"
            "Du bist ein Test-Assistent.\n"
            "</new_skill_content>\n\n"
            "Viel Spaß damit!"
        )
        result = extract_skill_content(llm_output)
        assert result.startswith("# test-skill")
        assert "**Trigger**: /test" in result
        assert "Viel Spaß" not in result
        assert "<new_skill_content>" not in result

    def test_GIVEN_markdown_codeblock_WHEN_extracted_THEN_fallback_works(self):
        """
        GIVEN  LLM-Output mit ```markdown Code-Block (kein XML)
        WHEN   extract_skill_content() aufgerufen wird
        THEN   Fallback auf ```markdown Extraktion
        """
        llm_output = "```markdown\n# my-skill\n\n**Trigger**: /my\n\n## System Prompt\n\nDu bist cool.\n```"
        result = extract_skill_content(llm_output)
        assert "# my-skill" in result

    def test_GIVEN_output_starting_with_h1_WHEN_extracted_THEN_uses_fallback(self):
        """
        GIVEN  LLM-Output der direkt mit '# skill-name' beginnt
        WHEN   extract_skill_content() aufgerufen wird
        THEN   Der gesamte Output wird als Skill-Markdown behandelt
        """
        llm_output = "# direct-skill\n\n**Trigger**: /direct\n\n## System Prompt\n\nDirekt."
        result = extract_skill_content(llm_output)
        assert result == llm_output.strip()

    def test_GIVEN_output_without_tags_WHEN_extracted_THEN_raises_error(self):
        """
        GIVEN  LLM-Output ohne XML-Tags und ohne Markdown-Block
        WHEN   extract_skill_content() aufgerufen wird
        THEN   SkillLoadError wird geworfen
        """
        with pytest.raises(SkillLoadError, match="weder"):
            extract_skill_content("Hier ist etwas Text ohne Skill-Format.")

    def test_GIVEN_legacy_alias_WHEN_called_THEN_works(self):
        """extract_skill_markdown ist ein Alias für extract_skill_content."""
        assert extract_skill_markdown is extract_skill_content


# ---------------------------------------------------------------------------
# extract_skill_filename Tests
# ---------------------------------------------------------------------------

class TestExtractSkillFilename:
    """Dateiname aus <skill_filename>-Tag."""

    def test_GIVEN_xml_tag_WHEN_extracted_THEN_returns_filename(self):
        output = "Text <skill_filename>fastapi-expert.md</skill_filename> Text"
        assert extract_skill_filename(output) == "fastapi-expert.md"

    def test_GIVEN_no_tag_WHEN_extracted_THEN_returns_none(self):
        assert extract_skill_filename("Kein Tag hier.") is None

    def test_GIVEN_dangerous_filename_WHEN_extracted_THEN_sanitized(self):
        """Path-Traversal im Dateinamen wird entfernt."""
        output = "<skill_filename>../../etc/passwd</skill_filename>"
        result = extract_skill_filename(output)
        assert "/" not in result
        assert ".." not in result


# ---------------------------------------------------------------------------
# extract_skill_name Tests
# ---------------------------------------------------------------------------

class TestExtractSkillName:
    """Skill-Name aus Markdown H1-Zeile."""

    def test_GIVEN_valid_h1_WHEN_extracted_THEN_returns_lowercase_name(self):
        assert extract_skill_name("# FastAPI Expert\n\nRest...") == "fastapi-expert"

    def test_GIVEN_already_lowercase_WHEN_extracted_THEN_returns_as_is(self):
        assert extract_skill_name("# my-cool-skill\n\n...") == "my-cool-skill"

    def test_GIVEN_no_h1_WHEN_extracted_THEN_raises_error(self):
        with pytest.raises(SkillLoadError, match="Header"):
            extract_skill_name("Kein Header hier.")


# ---------------------------------------------------------------------------
# Path-Traversal-Schutz Tests
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Sandboxing: kein Ausbruch aus dem Skills-Verzeichnis."""

    def test_GIVEN_normal_filename_WHEN_validated_THEN_returns_path(self, tmp_path):
        result = _validate_skill_path(tmp_path, "my-skill.md")
        assert result.name == "my-skill.md"
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_GIVEN_traversal_attack_WHEN_validated_THEN_only_basename(self, tmp_path):
        """../../core/chat.py wird auf chat.py reduziert (Path.name)."""
        result = _validate_skill_path(tmp_path, "../../core/chat.py")
        assert result.name == "chat.py"
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_GIVEN_hidden_file_WHEN_validated_THEN_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Ungültig"):
            _validate_skill_path(tmp_path, ".hidden")


# ---------------------------------------------------------------------------
# Überschreib-Schutz Tests
# ---------------------------------------------------------------------------

class TestUniqueSkillName:
    """Automatische Versionierung bei Namenskollisionen."""

    def test_GIVEN_name_not_exists_WHEN_checked_THEN_returns_unchanged(self, tmp_path):
        loader = SkillLoader(skills_dir=tmp_path)
        assert _unique_skill_name(loader, "new-skill") == "new-skill"

    def test_GIVEN_name_exists_WHEN_checked_THEN_returns_v2(self, tmp_path):
        loader = SkillLoader(skills_dir=tmp_path)
        # "writer" ist ein Built-in
        assert _unique_skill_name(loader, "writer") == "writer-v2"

    def test_GIVEN_name_and_v2_exist_WHEN_checked_THEN_returns_v3(self, tmp_path):
        loader = SkillLoader(skills_dir=tmp_path)
        # Built-in "writer" existiert → v2 erstellen
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "writer-v2.md").write_text(
            "# writer-v2\n\n**Trigger**: /writev2\n\n## System Prompt\n\nTest.\n"
        )
        assert _unique_skill_name(loader, "writer") == "writer-v3"


# ---------------------------------------------------------------------------
# build_skill Integration Tests
# ---------------------------------------------------------------------------

class TestBuildSkill:
    """Integration-Tests für build_skill()."""

    @pytest.mark.asyncio
    async def test_GIVEN_empty_topic_WHEN_build_THEN_raises_ValueError(self):
        with pytest.raises(ValueError, match="leer"):
            await build_skill(topic="", model="test-model")

    @pytest.mark.asyncio
    async def test_GIVEN_valid_topic_WHEN_build_THEN_creates_and_saves_skill(self, tmp_path):
        """
        GIVEN  Gültiges Topic + gemockter LLM-Output mit XML-Tags
        WHEN   build_skill() aufgerufen wird
        THEN   Skill wird erstellt, gespeichert und kann geladen werden
        """
        mock_output = (
            "<skill_filename>async-python.md</skill_filename>\n"
            "<new_skill_content>\n"
            "# async-python\n\n"
            "**Trigger**: /async\n"
            "**Description**: Hilft bei async/await Patterns.\n"
            "**Tools**: read_file\n\n"
            "## System Prompt\n\n"
            "Du bist ein Python-Async-Experte. Erkläre async/await Patterns klar.\n"
            "</new_skill_content>"
        )

        async def mock_chat(**kwargs):
            on_chunk = kwargs.get("on_chunk")
            if on_chunk:
                on_chunk(mock_output)

        loader = SkillLoader(skills_dir=tmp_path / "skills")

        with patch("core.skill_builder.chat_with_tools", side_effect=mock_chat):
            skill = await build_skill(
                topic="Wie wir async/await in Python nutzen",
                model="test-model",
                skills_loader=loader,
            )

        assert skill.name == "async-python"
        assert skill.trigger == "/async"
        assert "async" in skill.description.lower()
        assert (tmp_path / "skills" / "async-python.md").exists()

        # Kann vom Loader geladen werden
        loaded = loader.load("async-python")
        assert loaded.trigger == "/async"

    @pytest.mark.asyncio
    async def test_GIVEN_invalid_llm_output_WHEN_build_THEN_raises_SkillLoadError(self):
        async def mock_chat(**kwargs):
            on_chunk = kwargs.get("on_chunk")
            if on_chunk:
                on_chunk("Ich kann keinen Skill erstellen. Sorry.")

        with patch("core.skill_builder.chat_with_tools", side_effect=mock_chat):
            with pytest.raises(SkillLoadError):
                await build_skill(topic="Irgendwas", model="test-model")

    @pytest.mark.asyncio
    async def test_GIVEN_existing_skill_name_WHEN_build_THEN_auto_versions(self, tmp_path):
        """
        GIVEN  Ein Skill mit dem generierten Namen existiert bereits
        WHEN   build_skill() aufgerufen wird
        THEN   Der Name wird automatisch auf -v2 erweitert
        """
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        # Vorhandenen Skill erstellen
        (skills_dir / "my-skill.md").write_text(
            "# my-skill\n\n**Trigger**: /my\n\n## System Prompt\n\nAlt.\n"
        )

        mock_output = (
            "<new_skill_content>\n"
            "# my-skill\n\n"
            "**Trigger**: /my\n"
            "**Description**: Neuer Skill.\n"
            "**Tools**: web_search\n\n"
            "## System Prompt\n\n"
            "Neuer Prompt.\n"
            "</new_skill_content>"
        )

        async def mock_chat(**kwargs):
            on_chunk = kwargs.get("on_chunk")
            if on_chunk:
                on_chunk(mock_output)

        loader = SkillLoader(skills_dir=skills_dir)

        with patch("core.skill_builder.chat_with_tools", side_effect=mock_chat):
            skill = await build_skill(
                topic="Irgendwas", model="test-model", skills_loader=loader,
            )

        # Automatisch versioniert
        assert skill.name == "my-skill-v2"
        assert (skills_dir / "my-skill-v2.md").exists()
        # Original unverändert
        assert (skills_dir / "my-skill.md").exists()


# ---------------------------------------------------------------------------
# Scan-Limit Test
# ---------------------------------------------------------------------------

class TestScanLimit:
    """Kontext-Limit für Code-Scanning."""

    def test_GIVEN_max_scan_files_THEN_is_5(self):
        assert MAX_SCAN_FILES == 5


# ---------------------------------------------------------------------------
# Command Detection Tests
# ---------------------------------------------------------------------------

class TestLearnCommand:
    """Tests für /learn Command-Erkennung."""

    def test_GIVEN_learn_command_WHEN_checked_THEN_detected(self):
        assert is_learn_command("/learn FastAPI patterns")
        assert is_learn_command("/learn")
        assert is_learn_command("  /learn  etwas  ")

    def test_GIVEN_other_command_WHEN_checked_THEN_not_detected(self):
        assert not is_learn_command("/post something")
        assert not is_learn_command("hello world")

    def test_GIVEN_learn_with_topic_WHEN_extracted_THEN_returns_topic(self):
        assert extract_learn_topic("/learn FastAPI patterns") == "FastAPI patterns"

    def test_GIVEN_learn_without_topic_WHEN_extracted_THEN_returns_empty(self):
        assert extract_learn_topic("/learn") == ""

    def test_GIVEN_learn_command_WHEN_completions_THEN_included(self):
        assert "/learn" in get_completions("/le")

    def test_GIVEN_learn_command_WHEN_is_command_THEN_true(self):
        assert is_command("/learn something")
