"""
◑ MiMi Nox – Vision & Workspace Tool Tests
tests/test_vision.py

TDD Tests für analyze_image und load_workspace.
When/Given/Then Spezifikationen.
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools import (
    analyze_image,
    load_workspace,
    FileNotAllowedError,
    DirectoryNotFoundError,
    SUPPORTED_IMAGE_EXTENSIONS,
    MAX_WORKSPACE_CHARS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Erlaubtes Test-Verzeichnis innerhalb der Whitelist
_TEST_TMP = Path.home() / "tmp"
_TEST_TMP.mkdir(exist_ok=True)


def _create_minimal_png(path: Path) -> None:
    """Erstellt eine minimale valide PNG-Datei (1x1 Pixel, rot)."""
    # Minimaler PNG Header + IHDR + IDAT + IEND
    header = b'\x89PNG\r\n\x1a\n'
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBB B', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = 0x1CFC26  # pre-computed for 1x1 RGB
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    # Write minimal valid PNG-ish bytes (good enough for base64 test)
    path.write_bytes(header + ihdr)


# ---------------------------------------------------------------------------
# analyze_image Tests
# ---------------------------------------------------------------------------

class TestAnalyzeImage:
    """Vision-Tool für Bildanalyse."""

    @pytest.mark.asyncio
    async def test_GIVEN_path_outside_whitelist_WHEN_called_THEN_raises_FileNotAllowedError(self):
        """
        GIVEN ein Bildpfad außerhalb der Whitelist (z.B. /etc/secret.png)
        WHEN  analyze_image() aufgerufen wird
        THEN  FileNotAllowedError wird geworfen
        """
        with pytest.raises(FileNotAllowedError):
            await analyze_image(path="/etc/secret.png")

    @pytest.mark.asyncio
    async def test_GIVEN_nonexistent_image_WHEN_called_THEN_raises_FileNotFoundError(self):
        """
        GIVEN ein Pfad der nicht existiert (innerhalb der Whitelist)
        WHEN  analyze_image() aufgerufen wird
        THEN  FileNotFoundError wird geworfen
        """
        with pytest.raises(FileNotFoundError):
            await analyze_image(path=str(_TEST_TMP / "nonexistent_image_xyz.png"))

    @pytest.mark.asyncio
    async def test_GIVEN_non_image_file_WHEN_called_THEN_returns_error_message(self):
        """
        GIVEN eine .txt Datei statt einem Bild
        WHEN  analyze_image() aufgerufen wird
        THEN  Rückgabe enthält Fehlermeldung "Nicht unterstütztes Bildformat"
        """
        with tempfile.NamedTemporaryFile(suffix=".txt", dir=str(_TEST_TMP), delete=False) as f:
            f.write(b"Hello World")
            tmp_path = f.name

        try:
            result = await analyze_image(path=tmp_path)
            assert "Nicht unterstütztes Bildformat" in result
            assert ".txt" in result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_GIVEN_valid_image_WHEN_called_THEN_calls_ollama_with_base64(self):
        """
        GIVEN ein gültiges Bild im erlaubten Verzeichnis
        WHEN  analyze_image() aufgerufen wird
        THEN  Ollama wird mit Base64-encodiertem Bild aufgerufen
        """
        with tempfile.NamedTemporaryFile(suffix=".png", dir=str(_TEST_TMP), delete=False) as f:
            _create_minimal_png(Path(f.name))
            tmp_path = f.name

        mock_response = MagicMock()
        mock_response.message.content = "Ein rotes Pixel."

        try:
            with patch("core.tools.ollama.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.chat = AsyncMock(return_value=mock_response)
                MockClient.return_value = instance

                result = await analyze_image(path=tmp_path)

                assert result == "Ein rotes Pixel."
                # Verify chat was called with images parameter
                call_args = instance.chat.call_args
                assert "images" in call_args.kwargs.get("messages", [{}])[0]
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_GIVEN_supported_extensions_THEN_contains_common_formats(self):
        """
        GIVEN die SUPPORTED_IMAGE_EXTENSIONS
        THEN  PNG, JPG, JPEG, WebP sind enthalten
        """
        assert ".png" in SUPPORTED_IMAGE_EXTENSIONS
        assert ".jpg" in SUPPORTED_IMAGE_EXTENSIONS
        assert ".jpeg" in SUPPORTED_IMAGE_EXTENSIONS
        assert ".webp" in SUPPORTED_IMAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# load_workspace Tests
# ---------------------------------------------------------------------------

class TestLoadWorkspace:
    """Workspace-Loader für 128K Context."""

    @pytest.mark.asyncio
    async def test_GIVEN_directory_with_files_WHEN_load_workspace_THEN_returns_concatenated_content(self):
        """
        GIVEN ein Verzeichnis mit Python-Dateien
        WHEN  load_workspace(path, extensions=[".py"]) aufgerufen wird
        THEN  Rückgabe enthält Inhalt aller Dateien mit Pfad-Headern
        """
        with tempfile.TemporaryDirectory(dir=str(_TEST_TMP)) as tmpdir:
            # Create test files
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "utils.py").write_text("def add(a, b): return a + b")
            (Path(tmpdir) / "readme.md").write_text("# Test")  # Should be filtered

            result = await load_workspace(tmpdir, extensions=[".py"])

            assert "main.py" in result
            assert "utils.py" in result
            assert "print('hello')" in result
            assert "def add(a, b)" in result
            assert "readme.md" not in result  # Filtered by extension

    @pytest.mark.asyncio
    async def test_GIVEN_directory_outside_whitelist_WHEN_called_THEN_raises_error(self):
        """
        GIVEN ein Pfad außerhalb der Whitelist
        WHEN  load_workspace() aufgerufen wird
        THEN  FileNotAllowedError wird geworfen
        """
        with pytest.raises(FileNotAllowedError):
            await load_workspace(path="/etc/")

    @pytest.mark.asyncio
    async def test_GIVEN_nonexistent_directory_WHEN_called_THEN_raises_error(self):
        """
        GIVEN ein nicht existierendes Verzeichnis (innerhalb der Whitelist)
        WHEN  load_workspace() aufgerufen wird
        THEN  DirectoryNotFoundError wird geworfen
        """
        with pytest.raises(DirectoryNotFoundError):
            await load_workspace(path=str(_TEST_TMP / "nonexistent_dir_xyz_123"))

    @pytest.mark.asyncio
    async def test_GIVEN_empty_directory_WHEN_called_THEN_returns_no_files_message(self):
        """
        GIVEN ein leeres Verzeichnis
        WHEN  load_workspace() aufgerufen wird
        THEN  Rückgabe enthält "Keine passenden Dateien"
        """
        with tempfile.TemporaryDirectory(dir=str(_TEST_TMP)) as tmpdir:
            result = await load_workspace(tmpdir, extensions=[".xyz"])
            assert "Keine passenden Dateien" in result

    @pytest.mark.asyncio
    async def test_GIVEN_nested_directories_WHEN_called_THEN_reads_recursively(self):
        """
        GIVEN verschachtelte Verzeichnisse mit Dateien
        WHEN  load_workspace() aufgerufen wird
        THEN  Dateien aus Unter-Verzeichnissen werden auch geladen
        """
        with tempfile.TemporaryDirectory(dir=str(_TEST_TMP)) as tmpdir:
            base = Path(tmpdir)
            sub = base / "subdir"
            sub.mkdir()
            (base / "root.py").write_text("root_content")
            (sub / "nested.py").write_text("nested_content")

            result = await load_workspace(tmpdir, extensions=[".py"])

            assert "root_content" in result
            assert "nested_content" in result

    @pytest.mark.asyncio
    async def test_GIVEN_hidden_files_WHEN_called_THEN_skips_them(self):
        """
        GIVEN Verzeichnis mit versteckten Dateien (.gitignore)
        WHEN  load_workspace() aufgerufen wird
        THEN  Versteckte Dateien werden übersprungen
        """
        with tempfile.TemporaryDirectory(dir=str(_TEST_TMP)) as tmpdir:
            (Path(tmpdir) / ".gitignore").write_text("node_modules/")
            (Path(tmpdir) / "visible.py").write_text("visible_content")

            result = await load_workspace(tmpdir)

            assert "visible_content" in result
            assert ".gitignore" not in result
