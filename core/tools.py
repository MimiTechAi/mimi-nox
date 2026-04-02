"""
◑ MiMi Nox – Tool Engine
core/tools.py

Alle Tool-Funktionen für Tool Calling via Ollama.

Sicherheitsmodell:
  - web_search, file_search, get_datetime:  read-only, immer sicher
  - read_file, list_directory:             nur erlaubte Pfade (Whitelist)
  - run_shell:                             IMMER ShellConfirmationRequired
  - execute_confirmed_shell:               nur nach expliziter Bestätigung

Ollama-Integration:
  get_tool_schemas() → JSON-Schema Liste für ollama.chat(tools=...)

Plattform-Support:
  - macOS:   mdfind (Spotlight) für file_search
  - Linux:   find für file_search
  - Windows: where für file_search (basic)
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ddgs import DDGS


# ===========================================================================
# Custom Exceptions
# ===========================================================================

class WebSearchError(Exception):
    """DuckDuckGo nicht erreichbar oder anderer Suchfehler."""


class FileNotAllowedError(PermissionError):
    """Pfad ist nicht in der erlaubten Whitelist."""
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"Zugriff verweigert: '{path}' ist nicht in den erlaubten Verzeichnissen.\n"
            f"Erlaubt: HOME, Desktop, Documents, Downloads, tmp"
        )


class DirectoryNotFoundError(FileNotFoundError):
    """Verzeichnis existiert nicht."""
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Verzeichnis nicht gefunden: '{path}'")


class ShellConfirmationRequired(Exception):
    """
    Wird von run_shell() geworfen.
    Signalisiert der App: "User muss bestätigen bevor ausgeführt wird."
    """
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Bestätigung erforderlich für: {command}")


class ShellTimeoutError(TimeoutError):
    """Befehl hat das Timeout überschritten."""
    def __init__(self, command: str, timeout: int) -> None:
        self.command = command
        self.timeout = timeout
        super().__init__(f"Befehl '{command}' timed out nach {timeout}s")


# ===========================================================================
# Whitelist
# ===========================================================================

SHELL_TIMEOUT_SECONDS = 30

MAX_FILE_CHARS = 50_000


def _get_allowed_roots() -> list[Path]:
    """Rückgabe der erlaubten Basis-Verzeichnisse (Whitelist)."""
    home = Path.home()
    return [
        home,
        home / "Desktop",
        home / "Documents",
        home / "Dokumente",
        home / "Downloads",
        home / "tmp",
        Path("/tmp"),
        Path(os.environ.get("TMPDIR", "/tmp")),
    ]


def _is_path_allowed(path: Path) -> bool:
    """Gibt True zurück wenn path innerhalb einer erlaubten Wurzel liegt."""
    resolved = path.resolve()
    for root in _get_allowed_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


# ===========================================================================
# Tool: web_search
# ===========================================================================

async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Sucht im Internet via DuckDuckGo (ddgs).

    Returns:
        Liste von dicts mit keys: title, url, body

    Raises:
        ValueError:      leerer Query
        WebSearchError:  Netzwerk nicht erreichbar
    """
    query = query.strip()
    if not query:
        raise ValueError("Query darf nicht leer sein")

    def _search() -> list[dict]:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)
        return raw or []

    try:
        raw = await asyncio.to_thread(_search)
        return [
            {
                "title": r.get("title", ""),
                "url":   r.get("href", ""),
                "body":  r.get("body", ""),
            }
            for r in raw
        ]
    except Exception as exc:
        raise WebSearchError(str(exc)) from exc


# ===========================================================================
# Tool: file_search
# ===========================================================================

async def file_search(query: str, path: str | None = None) -> str:
    """
    Durchsucht das Dateisystem nach Dateien (macOS: mdfind, Linux: find).

    Returns:
        Newline-getrennte Liste gefundener Pfade als String

    Raises:
        ValueError: leerer Query
    """
    query = query.strip()
    if not query:
        raise ValueError("Query darf nicht leer sein")

    search_path = path or str(Path.home())

    try:
        if sys.platform == "darwin":
            cmd = ["mdfind", "-name", query]
            if path:
                cmd += ["-onlyin", search_path]
        elif sys.platform.startswith("win"):
            cmd = ["where", "/R", search_path, f"*{query}*"]
        else:
            # Linux / andere Unix
            cmd = ["find", search_path, "-iname", f"*{query}*", "-maxdepth", "10"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout.strip()
        return output if output else f"Keine Dateien für '{query}' gefunden."

    except subprocess.TimeoutExpired:
        return f"Suche nach '{query}' hat zu lange gedauert."
    except FileNotFoundError:
        # mdfind/find nicht verfügbar
        return f"Dateisuche nicht verfügbar auf diesem System ({sys.platform})."


# ===========================================================================
# Tool: read_file
# ===========================================================================

async def read_file(path: str) -> str:
    """
    Liest eine Datei und gibt den Inhalt zurück.

    Sicherheit: Nur Dateien innerhalb der Whitelist erlaubt.
    Große Dateien werden auf MAX_FILE_CHARS gekürzt.

    Raises:
        FileNotAllowedError:  Pfad außerhalb Whitelist
        FileNotFoundError:    Datei existiert nicht
    """
    # Tilde expandieren
    resolved = Path(path).expanduser()

    if not _is_path_allowed(resolved):
        raise FileNotAllowedError(str(resolved))

    if not resolved.exists():
        raise FileNotFoundError(
            f"Datei nicht gefunden: '{resolved}'"
        )

    content = resolved.read_text(encoding="utf-8", errors="replace")

    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS]
        content += f"\n\n[Datei gekürzt: Original hatte mehr als {MAX_FILE_CHARS} Zeichen]"

    return content


# ===========================================================================
# Tool: list_directory
# ===========================================================================

async def list_directory(path: str) -> list[str]:
    """
    Listet Inhalte eines Verzeichnisses auf.

    Sicherheit: Nur Pfade innerhalb der Whitelist erlaubt.

    Raises:
        FileNotAllowedError:    Pfad außerhalb Whitelist
        DirectoryNotFoundError: Verzeichnis existiert nicht
    """
    resolved = Path(path).expanduser()

    if not _is_path_allowed(resolved):
        raise FileNotAllowedError(str(resolved))

    if not resolved.exists():
        raise DirectoryNotFoundError(str(resolved))

    return [entry.name for entry in sorted(resolved.iterdir())]


# ===========================================================================
# Tool: get_datetime
# ===========================================================================

GERMAN_WEEKDAYS = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]

GERMAN_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


async def get_datetime() -> str:
    """
    Gibt aktuelles Datum und Uhrzeit auf Deutsch zurück.

    Returns:
        z.B. "Donnerstag, 02. April 2026, 19:45 Uhr"
    """
    now = datetime.now()
    weekday = GERMAN_WEEKDAYS[now.weekday()]
    month = GERMAN_MONTHS[now.month - 1]
    return f"{weekday}, {now.day:02d}. {month} {now.year}, {now.hour:02d}:{now.minute:02d} Uhr"


# ===========================================================================
# Tool: run_shell (IMMER Bestätigung erforderlich)
# ===========================================================================

async def run_shell(command: str) -> str:
    """
    SICHERHEITS-GATE: Wirft immer ShellConfirmationRequired.

    Diese Funktion führt NIE direkt aus.
    Die App muss den User fragen und dann execute_confirmed_shell() aufrufen.

    Raises:
        ShellConfirmationRequired: immer
    """
    raise ShellConfirmationRequired(command)


async def execute_confirmed_shell(command: str, confirmed: bool) -> str:
    """
    Führt einen Shell-Befehl aus — NUR wenn confirmed=True.

    Args:
        command:   Der Shell-Befehl
        confirmed: Muss explizit True sein (User hat bestätigt)

    Returns:
        stdout + stderr kombiniert als String

    Raises:
        ShellTimeoutError: wenn Befehl > SHELL_TIMEOUT_SECONDS dauert
    """
    if not confirmed:
        return "Abgebrochen."

    try:
        result = subprocess.run(
            command,
            shell=True,          # noqa: S602
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT_SECONDS,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip()
            return f"{output}\n[exit {result.returncode}] {error}".strip()
        return output or "(kein Output)"

    except subprocess.TimeoutExpired:
        raise ShellTimeoutError(command, SHELL_TIMEOUT_SECONDS)


# ===========================================================================
# Tool Execution Router
# ===========================================================================

TOOL_MAP: dict[str, object] = {
    "web_search":       web_search,
    "file_search":      file_search,
    "read_file":        read_file,
    "list_directory":   list_directory,
    "get_datetime":     get_datetime,
    "run_shell":        run_shell,
}


async def execute_tool(name: str, arguments: dict) -> str:
    """
    Führt ein Tool per Name aus und gibt das Ergebnis als String zurück.
    Fehler werden abgefangen und als String zurückgegeben — kein Crash.
    """
    func = TOOL_MAP.get(name)
    if func is None:
        return f"[Tool '{name}' nicht gefunden]"

    try:
        result = await func(**arguments)  # type: ignore[operator]
        if isinstance(result, list):
            return "\n".join(str(r) for r in result)
        return str(result)
    except ShellConfirmationRequired:
        raise  # App muss das handhaben
    except Exception as exc:
        return f"[Tool-Fehler '{name}': {exc}]"


# ===========================================================================
# Ollama Tool Schemas
# ===========================================================================

def get_tool_schemas() -> list[dict]:
    """
    Gibt alle Tool-Definitionen als Ollama-kompatible JSON-Schemas zurück.
    Wird an ollama.chat(tools=...) übergeben.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Sucht im Internet nach aktuellen Informationen via DuckDuckGo. "
                    "Nutze dieses Tool wenn der User nach aktuellen Ereignissen, "
                    "Fakten oder Informationen fragt die du nicht kennst."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Die Suchanfrage z.B. 'Python asyncio tutorial 2026'",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Anzahl der Ergebnisse (Standard: 5, max: 10)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_search",
                "description": (
                    "Durchsucht den Computer nach Dateien (macOS: Spotlight, Linux: find). "
                    "Nutze dieses Tool wenn der User eine Datei auf seinem Computer sucht."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Dateiname oder Suchbegriff z.B. 'Rechnung 2026' oder 'resume.pdf'",
                        },
                        "path": {
                            "type": "string",
                            "description": "Optionaler Startpfad für die Suche z.B. '~/Desktop'",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    "Liest den Inhalt einer Datei. "
                    "Nutze dieses Tool wenn der User eine Datei lesen, analysieren oder erklären möchte. "
                    "Sicherheit: Nur Dateien im Home-Verzeichnis, Desktop, Documents, Downloads erlaubt."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absoluter oder ~-relativer Pfad z.B. '~/Desktop/vertrag.txt'",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": (
                    "Listet den Inhalt eines Verzeichnisses auf. "
                    "Nutze dieses Tool wenn der User wissen möchte was in einem Ordner ist."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Pfad zum Verzeichnis z.B. '~/Desktop' oder '~/Documents'",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_datetime",
                "description": (
                    "Gibt das aktuelle Datum und die Uhrzeit auf Deutsch zurück. "
                    "Nutze dieses Tool wenn der User nach Datum, Uhrzeit oder Wochentag fragt."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_shell",
                "description": (
                    "Schlägt einen Terminal-Befehl vor der der User ausführen kann. "
                    "WICHTIG: Der Befehl wird NICHT automatisch ausgeführt. "
                    "Der User muss explizit zustimmen. "
                    "Nutze dieses Tool für git, docker, npm, oder andere CLI-Befehle."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Der Terminal-Befehl z.B. 'git status' oder 'npm install'",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
    ]
