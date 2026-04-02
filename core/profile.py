"""
◑ MiMi Nox – User Profile
core/profile.py

Persistentes Nutzerprofil. Lernt Präferenzen über Zeit.

Speicherpfad: ~/.mimi-nox/memory/user_profile.json (Standard)
              Oder beliebiger path (für Tests)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_PATH = Path.home() / ".mimi-nox" / "memory" / "user_profile.json"


@dataclass
class UserProfile:
    """Persistentes Nutzerprofil für MiMi Nox."""

    name: str | None = None
    expertise: str | None = None
    preferred_language: str | None = None
    response_style: str | None = None       # z.B. "kurz und direkt", "ausführlich"
    topics_of_interest: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """
        Gibt das Profil als System-Prompt-Kontext-String zurück.
        Wird vor jeder Antwort als zusätzlicher Kontext eingefügt.
        """
        parts: list[str] = ["[Nutzerprofil]"]

        if self.name:
            parts.append(f"Name: {self.name}")
        if self.expertise:
            parts.append(f"Expertise: {self.expertise}")
        if self.preferred_language:
            parts.append(f"Bevorzugte Sprache: {self.preferred_language}")
        if self.response_style:
            parts.append(f"Antwort-Stil: {self.response_style}")
        if self.topics_of_interest:
            parts.append(f"Interessengebiete: {', '.join(self.topics_of_interest)}")
        if self.projects:
            parts.append(f"Aktuelle Projekte: {', '.join(self.projects)}")
        if self.dislikes:
            parts.append(f"Bitte vermeiden: {', '.join(self.dislikes)}")

        if len(parts) == 1:
            return ""  # Nur der Header, kein Inhalt → leer zurückgeben

        return "\n".join(parts)

    def is_empty(self) -> bool:
        """True wenn kein Feld gesetzt."""
        return (
            self.name is None
            and self.expertise is None
            and self.preferred_language is None
            and self.response_style is None
            and not self.topics_of_interest
            and not self.projects
            and not self.dislikes
        )


# ---------------------------------------------------------------------------
# IO Functions
# ---------------------------------------------------------------------------

def load_profile(path: Path | None = None) -> UserProfile:
    """
    Lädt das Nutzerprofil aus einer JSON-Datei.

    Returns default UserProfile bei:
      - Datei nicht vorhanden
      - Korruptes JSON
      - Falsches Format
    """
    profile_path = Path(path or DEFAULT_PROFILE_PATH)

    if not profile_path.exists():
        return UserProfile()

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Profil-Datei hat ungültiges Format, nutze Default.")
            return UserProfile()

        return UserProfile(
            name=data.get("name"),
            expertise=data.get("expertise"),
            preferred_language=data.get("preferred_language"),
            response_style=data.get("response_style"),
            topics_of_interest=data.get("topics_of_interest", []),
            projects=data.get("projects", []),
            dislikes=data.get("dislikes", []),
        )
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Profil konnte nicht gelesen werden: %s. Nutze Default.", exc)
        return UserProfile()


def save_profile(profile: UserProfile, path: Path | None = None) -> None:
    """
    Speichert das Nutzerprofil als JSON-Datei.
    Erstellt fehlende Verzeichnisse automatisch.
    """
    profile_path = Path(path or DEFAULT_PROFILE_PATH)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(asdict(profile), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_profile(updates: dict[str, Any], path: Path | None = None) -> UserProfile:
    """
    Aktualisiert einzelne Felder des Nutzerprofils.
    Lädt, updated, speichert.

    Returns:
        Das aktualisierte UserProfile
    """
    profile = load_profile(path=path)

    for key, value in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    save_profile(profile, path=path)
    return profile
