"""
◑ MiMi Nox – Feedback System (👍 / 👎)
core/feedback.py

Speichert positive und negative Antwort-Beispiele.
Positive Beispiele werden als Few-Shot-Kontext vor Antworten eingefügt
um den Stil an die Nutzer-Präferenzen anzupassen.

Speicherpfad:
  ~/.mimi-nox/memory/good_examples/  (👍)
  ~/.mimi-nox/memory/bad_examples/   (👎)

Format: JSON-Dateien, eine pro Beispiel.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_BASE_DIR = Path.home() / ".mimi-nox" / "memory"


@dataclass
class FeedbackExample:
    """Ein Feedback-Beispiel (Prompt + Response-Paar)."""
    prompt: str
    response: str
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class FeedbackStore:
    """
    Speichert 👍/👎 Feedback und liefert Few-Shot-Beispiele.

    Usage:
        store = FeedbackStore()
        store.thumbs_up(prompt="Was ist Python?", response="Eine Programmiersprache...")
        examples = store.get_good_examples(max_items=3)
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = Path(base_dir or DEFAULT_BASE_DIR)
        self._good_dir = self._base / "good_examples"
        self._bad_dir = self._base / "bad_examples"

    # ── Public API ────────────────────────────────────────────────────────────

    def thumbs_up(self, prompt: str, response: str) -> None:
        """Speichert ein positives Beispiel (👍)."""
        self._save(FeedbackExample(prompt=prompt, response=response), self._good_dir)

    def thumbs_down(self, prompt: str, response: str) -> None:
        """Speichert ein negatives Beispiel (👎)."""
        self._save(FeedbackExample(prompt=prompt, response=response), self._bad_dir)

    def get_good_examples(self, max_items: int = 5) -> list[FeedbackExample]:
        """
        Gibt die neuesten positiven Beispiele zurück.

        Returns:
            Liste von FeedbackExample-Objekten, neueste zuerst.
        """
        return self._load_from(self._good_dir, max_items)

    def get_bad_examples(self, max_items: int = 5) -> list[FeedbackExample]:
        """Gibt die neuesten negativen Beispiele zurück."""
        return self._load_from(self._bad_dir, max_items)

    def count_good(self) -> int:
        """Anzahl gespeicherter positiver Beispiele."""
        return self._count(self._good_dir)

    def count_bad(self) -> int:
        """Anzahl gespeicherter negativer Beispiele."""
        return self._count(self._bad_dir)

    def to_few_shot_string(self, max_items: int = 3) -> str:
        """
        Gibt positive Beispiele als Few-Shot-Kontext für den System-Prompt zurück.

        Returns:
            Formatierter String mit Beispielen, oder "" wenn keine vorhanden.
        """
        examples = self.get_good_examples(max_items=max_items)
        if not examples:
            return ""

        lines = ["[Beispiele für bevorzugten Antwort-Stil:]"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"\nBeispiel {i}:")
            lines.append(f"Frage: {ex.prompt[:200]}")
            lines.append(f"Antwort: {ex.response[:300]}")

        return "\n".join(lines)

    # ── Private ────────────────────────────────────────────────────────────────

    def _save(self, example: FeedbackExample, directory: Path) -> None:
        """Speichert ein Beispiel als JSON-Datei mit eindeutigem Namen."""
        directory.mkdir(parents=True, exist_ok=True)
        # Mikrosekunden + Hash für Eindeutigkeit auch bei schnellen Tests
        unique = hashlib.sha256(
            f"{example.timestamp}:{example.prompt}:{example.response}".encode()
        ).hexdigest()[:8]
        filename = directory / f"{int(example.timestamp * 1_000_000)}_{unique}.json"
        filename.write_text(
            json.dumps(asdict(example), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_from(self, directory: Path, max_items: int) -> list[FeedbackExample]:
        """Lädt Beispiele aus einem Verzeichnis, neueste zuerst."""
        if not directory.exists():
            return []

        files = sorted(directory.glob("*.json"), reverse=True)[:max_items]
        examples: list[FeedbackExample] = []

        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                examples.append(FeedbackExample(
                    prompt=data.get("prompt", ""),
                    response=data.get("response", ""),
                    timestamp=data.get("timestamp", 0.0),
                ))
            except Exception:
                continue  # Korrupte Datei überspringen

        return examples

    def _count(self, directory: Path) -> int:
        """Zählt JSON-Dateien in einem Verzeichnis."""
        if not directory.exists():
            return 0
        return len(list(directory.glob("*.json")))
