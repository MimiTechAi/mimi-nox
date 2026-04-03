"""
◑ MiMi Nox – Phase 1 TDD
tests/test_tools.py

REGEL: Tests wurden VOR der Implementierung geschrieben.
Alle Tests müssen ROT sein bis core/tools.py vollständig implementiert ist.

Given / When / Then – strikte Einhaltung.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Imports – schlagen fehl wenn core/tools.py noch nicht existiert (erwartet!)
# ---------------------------------------------------------------------------

from core.tools import (
    DirectoryNotFoundError,
    FileNotAllowedError,
    ShellConfirmationRequired,
    ShellTimeoutError,
    WebSearchError,
    execute_confirmed_shell,
    file_search,
    get_datetime,
    get_tool_schemas,
    list_directory,
    read_file,
    run_shell,
    web_search,
)


# ===========================================================================
# web_search
# ===========================================================================

class TestWebSearch:

    @pytest.mark.asyncio
    async def test_returns_results_on_success(self):
        """
        GIVEN  DuckDuckGo ist erreichbar (gemockt)
        WHEN   web_search("Python asyncio") aufgerufen
        THEN   Rückgabe ist Liste mit ≥1 Einträgen
        AND    Jeder Eintrag hat keys: title, url, body
        AND    body ist nicht-leerer String
        """
        mock_results = [
            {"title": "Python asyncio docs", "href": "https://docs.python.org", "body": "Asyncio is..."},
            {"title": "Real Python asyncio", "href": "https://realpython.com", "body": "Learn asyncio..."},
        ]
        mock_instance = MagicMock()
        mock_instance.text = MagicMock(return_value=mock_results)
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)

        with patch("core.tools.DDGS", return_value=mock_instance):
            results = await web_search("Python asyncio")

        assert isinstance(results, list)
        assert len(results) >= 1
        for entry in results:
            assert "title" in entry
            assert "url" in entry
            assert "body" in entry
            assert isinstance(entry["body"], str)
            assert len(entry["body"]) > 0

    @pytest.mark.asyncio
    async def test_raises_web_search_error_on_connection_failure(self):
        """
        GIVEN  DuckDuckGo nicht erreichbar (mock: ConnectionError)
        WHEN   web_search("irgendwas") aufgerufen
        THEN   Wirft WebSearchError mit verständlicher Meldung
        AND    App crasht NICHT
        """
        mock_instance = MagicMock()
        mock_instance.text = MagicMock(side_effect=ConnectionError("no connection"))
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)

        with patch("core.tools.DDGS", return_value=mock_instance):
            with pytest.raises(WebSearchError):
                await web_search("irgendwas")

    @pytest.mark.asyncio
    async def test_raises_value_error_on_empty_query(self):
        """
        GIVEN  Leerer Query-String
        WHEN   web_search("") aufgerufen
        THEN   Wirft ValueError("Query darf nicht leer sein")
        """
        with pytest.raises(ValueError, match="leer"):
            await web_search("")

    @pytest.mark.asyncio
    async def test_raises_value_error_on_whitespace_query(self):
        """
        GIVEN  Query nur aus Whitespace
        WHEN   web_search("   ") aufgerufen
        THEN   Wirft ValueError
        """
        with pytest.raises(ValueError):
            await web_search("   ")


# ===========================================================================
# file_search
# ===========================================================================

class TestFileSearch:

    @pytest.mark.asyncio
    async def test_returns_file_path_on_macos(self, tmp_path):
        """
        GIVEN  macOS + mdfind gibt Pfad zurück (gemockt)
        WHEN   file_search("test_mimi.pdf") aufgerufen
        THEN   Rückgabe enthält den Dateinamen
        AND    Rückgabe ist nicht-leerer String
        """
        fake_output = "/Users/test/Desktop/test_mimi.pdf\n"
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=fake_output, returncode=0
                )
                result = await file_search("test_mimi.pdf")

        assert "test_mimi.pdf" in result
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_falls_back_to_find_on_linux(self):
        """
        GIVEN  Linux System (sys.platform = "linux")
        WHEN   file_search("test.pdf") aufgerufen
        THEN   Fällt zurück auf `find`-Befehl (kein Crash)
        AND    subprocess.run wird mit 'find' aufgerufen
        """
        with patch("sys.platform", "linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="/home/user/test.pdf\n", returncode=0
                )
                result = await file_search("test.pdf")
                cmd = mock_run.call_args[0][0]

        assert "find" in cmd or "locate" in cmd
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_raises_value_error_on_empty_query(self):
        """
        GIVEN  Leerer Query-String
        WHEN   file_search("") aufgerufen
        THEN   Wirft ValueError
        """
        with pytest.raises(ValueError):
            await file_search("")


# ===========================================================================
# read_file
# ===========================================================================

class TestReadFile:

    @pytest.mark.asyncio
    async def test_reads_allowed_file(self, tmp_path):
        """
        GIVEN  Datei in HOME mit Inhalt "Hallo MiMi Nox"
        WHEN   read_file(path) aufgerufen
        THEN   Rückgabe enthält "Hallo MiMi Nox"
        AND    Rückgabe ist String
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hallo MiMi Nox", encoding="utf-8")

        # Patch HOME so tmp_path is inside whitelist
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = await read_file(str(test_file))

        assert "Hallo MiMi Nox" in result
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_raises_error_for_path_outside_whitelist(self):
        """
        GIVEN  Pfad außerhalb Whitelist: "/etc/passwd"
        WHEN   read_file("/etc/passwd") aufgerufen
        THEN   Wirft FileNotAllowedError
        AND    Datei wird NICHT geöffnet
        """
        with pytest.raises(FileNotAllowedError):
            await read_file("/etc/passwd")

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_file(self, tmp_path):
        """
        GIVEN  Datei existiert nicht
        WHEN   read_file(pfad_der_nicht_existiert) aufgerufen
        THEN   Wirft FileNotFoundError
        AND    Pfad ist in der Fehlermeldung
        """
        missing = tmp_path / "nicht_vorhanden.txt"
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            with pytest.raises(FileNotFoundError) as exc_info:
                await read_file(str(missing))

        assert "nicht_vorhanden" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_truncates_large_files(self, tmp_path):
        """
        GIVEN  Datei > 100.000 Zeichen (MAX_FILE_CHARS)
        WHEN   read_file(path) aufgerufen
        THEN   Rückgabe ist auf 100.000 Zeichen gekürzt
        AND    Meldung "[Datei gekürzt" ist angefügt
        """
        big_content = "x" * 120_000
        test_file = tmp_path / "big.txt"
        test_file.write_text(big_content, encoding="utf-8")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = await read_file(str(test_file))

        assert len(result) <= 100_100  # content + truncation note
        assert "gekürzt" in result.lower() or "truncated" in result.lower()


# ===========================================================================
# list_directory
# ===========================================================================

class TestListDirectory:

    @pytest.mark.asyncio
    async def test_returns_file_list_for_allowed_path(self, tmp_path):
        """
        GIVEN  Verzeichnis existiert und enthält ≥1 Dateien
        WHEN   list_directory(path) aufgerufen
        THEN   Rückgabe ist Liste von Dateinamen
        AND    Jeder Eintrag ist String
        """
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")

        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = await list_directory(str(tmp_path))

        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(e, str) for e in result)

    @pytest.mark.asyncio
    async def test_raises_error_for_path_outside_whitelist(self):
        """
        GIVEN  Pfad außerhalb Whitelist: "/etc/"
        WHEN   list_directory("/etc/") aufgerufen
        THEN   Wirft FileNotAllowedError
        """
        with pytest.raises(FileNotAllowedError):
            await list_directory("/etc/")

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_directory(self, tmp_path):
        """
        GIVEN  Verzeichnis existiert nicht
        WHEN   list_directory(nicht_vorhanden) aufgerufen
        THEN   Wirft DirectoryNotFoundError
        """
        missing = tmp_path / "nicht_vorhanden"
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            with pytest.raises(DirectoryNotFoundError):
                await list_directory(str(missing))


# ===========================================================================
# get_datetime
# ===========================================================================

class TestGetDatetime:

    @pytest.mark.asyncio
    async def test_returns_current_year(self):
        """
        GIVEN  Irgendein Zeitpunkt im Jahr 2026
        WHEN   get_datetime() aufgerufen
        THEN   Rückgabe enthält aktuelles Jahr (4-stellig)
        AND    Rückgabe enthält deutschen Wochentag
        AND    Rückgabe ist nicht-leerer String
        """
        result = await get_datetime()

        assert isinstance(result, str)
        assert len(result) > 0
        assert "2026" in result
        german_days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                       "Freitag", "Samstag", "Sonntag"]
        assert any(day in result for day in german_days)


# ===========================================================================
# run_shell / execute_confirmed_shell
# ===========================================================================

class TestRunShell:

    @pytest.mark.asyncio
    async def test_always_raises_confirmation_required(self):
        """
        GIVEN  Kein Confirmation-Handler
        WHEN   run_shell("ls") aufgerufen
        THEN   Wirft ShellConfirmationRequired(command="ls")
        AND    Befehl wird NICHT ausgeführt
        """
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ShellConfirmationRequired) as exc_info:
                await run_shell("ls")

            mock_run.assert_not_called()

        assert exc_info.value.command == "ls"

    @pytest.mark.asyncio
    async def test_execute_confirmed_runs_command(self):
        """
        GIVEN  Confirmation = True
        WHEN   execute_confirmed_shell("echo hello", confirmed=True)
        THEN   Rückgabe enthält stdout
        AND    exit_code ist 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\n", stderr="", returncode=0
            )
            result = await execute_confirmed_shell("echo hello", confirmed=True)

        assert "hello" in result
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_denied_returns_aborted(self):
        """
        GIVEN  Confirmation = False
        WHEN   execute_confirmed_shell("rm -rf /", confirmed=False)
        THEN   Rückgabe ist "Abgebrochen."
        AND    Befehl wird NICHT ausgeführt
        """
        with patch("subprocess.run") as mock_run:
            result = await execute_confirmed_shell("rm -rf /", confirmed=False)

        assert "Abgebrochen" in result
        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_captures_failed_command(self):
        """
        GIVEN  Befehl schlägt fehl (exit_code ≠ 0)
        WHEN   execute_confirmed_shell("ls /nicht_vorhanden", confirmed=True)
        THEN   Rückgabe enthält stderr
        AND    Kein Crash
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="", stderr="No such file or directory", returncode=1
            )
            result = await execute_confirmed_shell("ls /nicht_vorhanden", confirmed=True)

        assert isinstance(result, str)
        assert "No such file" in result or "exit" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_raises_timeout_error(self):
        """
        GIVEN  Befehl läuft länger als timeout (30s)
        WHEN   execute_confirmed_shell("sleep 60", confirmed=True)
        THEN   Wirft ShellTimeoutError nach 30s
        AND    Prozess wird terminiert
        """
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sleep 60", 30)):
            with pytest.raises(ShellTimeoutError):
                await execute_confirmed_shell("sleep 60", confirmed=True)


# ===========================================================================
# get_tool_schemas
# ===========================================================================

class TestToolSchemas:

    def test_returns_list_of_dicts(self):
        """
        GIVEN  Keine Vorbedingung
        WHEN   get_tool_schemas() aufgerufen
        THEN   Rückgabe ist Liste von dicts
        AND    Jedes dict hat "type" und "function" Keys
        AND    Jede "function" hat "name", "description", "parameters"
        """
        schemas = get_tool_schemas()

        assert isinstance(schemas, list)
        assert len(schemas) >= 5  # web_search, file_search, read_file, list_dir, get_datetime, run_shell

        for schema in schemas:
            assert schema["type"] == "function"
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert isinstance(func["description"], str)
            assert len(func["description"]) > 10

    def test_all_tool_names_match_functions(self):
        """
        GIVEN  Liste der definierten Tool-Funktionen
        WHEN   get_tool_schemas() aufgerufen
        THEN   Jeder Schema-Name entspricht einer importierbaren Funktion
        """
        import core.tools as tools_module
        schemas = get_tool_schemas()
        for schema in schemas:
            name = schema["function"]["name"]
            assert hasattr(tools_module, name), f"Tool '{name}' hat keine Implementierung"
