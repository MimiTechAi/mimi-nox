"""
◑ MiMi Nox – Artifact Detector
Erkennt Codeblöcke und andere strukturierte Inhalte im LLM-Output
und kapselt sie als Artifacts (wie Claude's Artifact-Panel).

TDD-spezifiziert in tests/test_artifact_detector.py
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Typen ─────────────────────────────────────────────────────────────────────

class ArtifactType(str, Enum):
    CODE_PYTHON = "code_python"
    CODE_BASH   = "code_bash"
    CODE_JS     = "code_js"
    CODE_TS     = "code_typescript"
    CODE_RUST   = "code_rust"
    CODE_GO     = "code_go"
    CODE_SQL    = "code_sql"
    CODE_OTHER  = "code_other"
    HTML        = "html"
    SVG         = "svg"
    MARKDOWN    = "markdown"
    JSON        = "json"
    YAML        = "yaml"
    DIFF        = "diff"


# Minimum Zeilen (~5 Code-Zeilen) damit Artifact erzeugt wird
ARTIFACT_LINE_THRESHOLD = 5

# Mapping: Sprache → ArtifactType
_LANG_MAP = {
    "python":     ArtifactType.CODE_PYTHON,
    "py":         ArtifactType.CODE_PYTHON,
    "bash":       ArtifactType.CODE_BASH,
    "sh":         ArtifactType.CODE_BASH,
    "shell":      ArtifactType.CODE_BASH,
    "javascript": ArtifactType.CODE_JS,
    "js":         ArtifactType.CODE_JS,
    "typescript": ArtifactType.CODE_TS,
    "ts":         ArtifactType.CODE_TS,
    "rust":       ArtifactType.CODE_RUST,
    "go":         ArtifactType.CODE_GO,
    "sql":        ArtifactType.CODE_SQL,
    "html":       ArtifactType.HTML,
    "svg":        ArtifactType.SVG,
    "json":       ArtifactType.JSON,
    "yaml":       ArtifactType.YAML,
    "yml":        ArtifactType.YAML,
    "diff":       ArtifactType.DIFF,
    "patch":      ArtifactType.DIFF,
    "markdown":   ArtifactType.MARKDOWN,
    "md":         ArtifactType.MARKDOWN,
}

# Sinnvolle Standard-Dateinamen pro Typ
_DEFAULT_FILENAMES = {
    ArtifactType.CODE_PYTHON: "script.py",
    ArtifactType.CODE_BASH:   "script.sh",
    ArtifactType.CODE_JS:     "script.js",
    ArtifactType.CODE_TS:     "script.ts",
    ArtifactType.CODE_RUST:   "main.rs",
    ArtifactType.CODE_GO:     "main.go",
    ArtifactType.CODE_SQL:    "query.sql",
    ArtifactType.CODE_OTHER:  "code.txt",
    ArtifactType.HTML:        "page.html",
    ArtifactType.SVG:         "image.svg",
    ArtifactType.MARKDOWN:    "document.md",
    ArtifactType.JSON:        "data.json",
    ArtifactType.YAML:        "config.yaml",
    ArtifactType.DIFF:        "changes.diff",
}


# ── Artifact Dataclass ─────────────────────────────────────────────────────────

@dataclass
class Artifact:
    artifact_type: ArtifactType
    content:       str
    language:      str
    title:         str
    filename:      str
    id:            str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "artifact_type": self.artifact_type.value,
            "content":       self.content,
            "language":      self.language,
            "title":         self.title,
            "filename":      self.filename,
        }


# ── ArtifactDetector ──────────────────────────────────────────────────────────

# Regex für Markdown-Codeblöcke: ```lang\n...\n```
_FENCE_RE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9+\-#]*)\n(?P<code>.*?)```",
    re.DOTALL
)


class ArtifactDetector:
    """
    Erkennt Artifacts in einer fertigen oder partiellen LLM-Antwort.
    Gibt Artifacts zurück und liefert den bereinigten Chat-Text (ohne Code).
    """

    def detect(self, text: str) -> list[Artifact]:
        """
        Gibt alle Artifacts zurück die ≥ ARTIFACT_LINE_THRESHOLD Zeilen haben.
        Kurze Inline-Blöcke (```kurz```) werden ignoriert.
        """
        artifacts: list[Artifact] = []
        for m in _FENCE_RE.finditer(text):
            lang = m.group("lang").strip().lower()
            code = m.group("code")

            # Zu kurze Blöcke ignorieren
            code_lines = [l for l in code.split("\n") if l.strip()]
            if len(code_lines) < ARTIFACT_LINE_THRESHOLD:
                continue

            artifact_type = _LANG_MAP.get(lang, ArtifactType.CODE_OTHER)
            filename      = _DEFAULT_FILENAMES.get(artifact_type, "code.txt")
            title         = self._generate_title(code, artifact_type, filename)

            artifacts.append(Artifact(
                artifact_type = artifact_type,
                content       = code.rstrip(),
                language      = lang or "text",
                title         = title,
                filename      = filename,
            ))

        return artifacts

    def extract_text(self, text: str) -> str:
        """
        Gibt den Chat-Text ohne Codeblöcke zurück.
        Codeblöcke ≥ Threshold werden durch einen Placeholder ersetzt.
        """
        def replace_block(m: re.Match) -> str:
            lang = m.group("lang").strip().lower()
            code = m.group("code")
            code_lines = [l for l in code.split("\n") if l.strip()]

            if len(code_lines) < ARTIFACT_LINE_THRESHOLD:
                return m.group(0)  # Kurze Blöcke unverändert lassen

            artifact_type = _LANG_MAP.get(lang, ArtifactType.CODE_OTHER)
            filename      = _DEFAULT_FILENAMES.get(artifact_type, "code.txt")
            return f"\n[📄 Artifact: **{filename}** öffnen]\n"

        return _FENCE_RE.sub(replace_block, text).strip()

    def split(self, text: str) -> list[dict]:
        """
        Gibt eine geordnete Liste von {"type": "text"|"artifact", "content": ...} zurück.
        Nützlich für schrittweises Streaming.
        """
        result: list[dict] = []
        last_end = 0

        for m in _FENCE_RE.finditer(text):
            lang = m.group("lang").strip().lower()
            code = m.group("code")
            code_lines = [l for l in code.split("\n") if l.strip()]

            # Text vor dem Block
            before = text[last_end:m.start()].strip()
            if before:
                result.append({"type": "text", "content": before})

            if len(code_lines) >= ARTIFACT_LINE_THRESHOLD:
                artifact_type = _LANG_MAP.get(lang, ArtifactType.CODE_OTHER)
                filename      = _DEFAULT_FILENAMES.get(artifact_type, "code.txt")
                result.append({
                    "type":     "artifact",
                    "artifact": Artifact(
                        artifact_type = artifact_type,
                        content       = code.rstrip(),
                        language      = lang or "text",
                        title         = self._generate_title(code, artifact_type, filename),
                        filename      = filename,
                    ).to_dict()
                })
            else:
                # Kurze Blöcke als Text ausgeben
                result.append({"type": "text", "content": m.group(0)})

            last_end = m.end()

        # Rest-Text nach dem letzten Block
        after = text[last_end:].strip()
        if after:
            result.append({"type": "text", "content": after})

        return result

    # ── Internes ──────────────────────────────────────────────────────────────

    def _generate_title(
        self,
        code:          str,
        artifact_type: ArtifactType,
        filename:      str,
    ) -> str:
        """Versucht einen sinnvollen Titel aus dem Code-Inhalt zu extrahieren."""
        first_lines = [l.strip() for l in code.split("\n") if l.strip()][:5]

        # Python: erste def oder class
        for line in first_lines:
            if line.startswith("def ") or line.startswith("class "):
                name = line.split("(")[0].split(" ")[1]
                return f"{name}() — {filename}"
            if line.startswith("# "):
                return line[2:].strip()

        # HTML: <title>
        title_match = re.search(r"<title>(.*?)</title>", code, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()

        # Fallback: Dateiname
        return filename
