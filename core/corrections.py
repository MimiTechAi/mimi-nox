"""
◑ MiMi Nox – Fehler-Journal / Correction Memory
core/corrections.py

Speichert Nutzer-Korrekturen persistent.
Wird als Kontext eingespeist um Wiederholung von Fehlern zu verhindern.

Speicherpfad: ~/.mimi-nox/memory/corrections.md (Standard)
Format: Markdown, Einträge neueste zuerst.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_CORRECTIONS_PATH = Path.home() / ".mimi-nox" / "memory" / "corrections.md"

ENTRY_SEPARATOR = "---"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Correction:
    """Ein einzelner Korrektur-Eintrag."""
    wrong: str
    correct: str
    timestamp: datetime


class CorrectionJournal:
    """
    Append-only Fehler-Journal.

    Speichert Korrekturen als Markdown-Datei.
    Unterstützt: add(), get_recent(), to_context_string()
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or DEFAULT_CORRECTIONS_PATH)

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, wrong: str, correct: str) -> None:
        """
        Fügt eine neue Korrektur hinzu (neueste zuerst).

        Args:
            wrong:   Was MiMi Nox falsch behauptet hat
            correct: Die richtige Information
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now().strftime(DATE_FORMAT)
        entry = (
            f"## {now}\n"
            f"**Falsch behauptet:** {wrong}\n"
            f"**Korrekt:** {correct}\n"
            f"{ENTRY_SEPARATOR}\n"
        )

        # Neueste Einträge oben (prepend)
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        self.path.write_text(entry + existing, encoding="utf-8")

    def get_recent(self, n: int) -> list[Correction]:
        """
        Gibt die n neuesten Korrekturen zurück.

        Returns:
            Liste von Correction-Objekten, neueste zuerst.
            Leere Liste wenn kein Journal vorhanden.
        """
        if not self.path.exists():
            return []

        content = self.path.read_text(encoding="utf-8")
        return self._parse(content)[:n]

    def to_context_string(self, max_items: int = 5) -> str:
        """
        Gibt die neuesten Korrekturen als System-Prompt-Kontext zurück.
        Wird vor jeder Antwort eingefügt um Fehler-Wiederholung zu vermeiden.
        """
        corrections = self.get_recent(max_items)
        if not corrections:
            return ""

        lines = ["[Bekannte Fehler – bitte vermeiden:]"]
        for c in corrections:
            lines.append(f"- Früher falsch: '{c.wrong}' → Korrekt: '{c.correct}'")

        return "\n".join(lines)

    # ── Private ────────────────────────────────────────────────────────────────

    def _parse(self, content: str) -> list[Correction]:
        """Parst Markdown-Inhalt in Correction-Objekte."""
        corrections: list[Correction] = []
        blocks = content.split(f"{ENTRY_SEPARATOR}\n")

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            wrong_match = re.search(r"\*\*Falsch behauptet:\*\*\s*(.+)", block)
            correct_match = re.search(r"\*\*Korrekt:\*\*\s*(.+)", block)
            date_match = re.search(r"## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", block)

            if not (wrong_match and correct_match):
                continue

            timestamp = datetime.now()
            if date_match:
                try:
                    timestamp = datetime.strptime(date_match.group(1), DATE_FORMAT)
                except ValueError:
                    pass

            corrections.append(Correction(
                wrong=wrong_match.group(1).strip(),
                correct=correct_match.group(1).strip(),
                timestamp=timestamp,
            ))

        return corrections
