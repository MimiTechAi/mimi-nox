"""
TDD Suite: Artifact Detection
Gegeben-Wenn-Dann (Given-When-Then) nach BDD-Manier
"""
import pytest
from core.artifact_detector import ArtifactDetector, ArtifactType


# ── Fixtures ──────────────────────────────────────────────────────────────────

PYTHON_BLOCK = """Ein Beispielskript:

```python
import os

def list_files(path):
    for f in os.listdir(path):
        print(f)

list_files('/tmp')
```

Das war alles."""

INLINE_CODE = "Setze `foo = 1` in deiner config."

HTML_BLOCK = """Hier die Webseite:

```html
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
  <h1>Hello World</h1>
  <p>Test Paragraph</p>
</body>
</html>
```
"""

SHORT_CODE = """Kurz:

```python
x = 1
```
"""

MULTIPLE_BLOCKS = (
    "Erst Python:\n\n"
    "```python\n"
    "def foo():\n"
    "    # Returns the answer to life\n"
    "    answer = 42\n"
    "    print(f'Answer: {answer}')\n"
    "    return answer\n"
    "\n"
    "result = foo()\n"
    "print(result)\n"
    "```\n\n"
    "Dann Bash:\n\n"
    "```bash\n"
    "echo 'Hello from Nox'\n"
    "ls -la /tmp\n"
    "cat ~/.bashrc\n"
    "grep -r 'foo' .\n"
    "find . -name '*.py' | head -10\n"
    "```\n"
)


# ── Test Suite 1: Typ-Erkennung ───────────────────────────────────────────────

class TestArtifactTypeDetection:

    def test_python_block_recognized(self):
        """G: Antwort mit Python-Block ≥5 Zeilen W: detector.detect() T: Typ ist CODE_PYTHON"""
        detector = ArtifactDetector()
        artifacts = detector.detect(PYTHON_BLOCK)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.CODE_PYTHON

    def test_html_block_recognized(self):
        """G: HTML-Block W: detect() T: Typ ist HTML"""
        detector = ArtifactDetector()
        artifacts = detector.detect(HTML_BLOCK)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.HTML

    def test_multiple_blocks_detected(self):
        """G: Zwei Code-Blöcke in einer Antwort T: Zwei Artifacts"""
        detector = ArtifactDetector()
        artifacts = detector.detect(MULTIPLE_BLOCKS)
        assert len(artifacts) == 2

    def test_inline_code_not_artifact(self):
        """G: Inline-Code-Span W: detect() T: Kein Artifact (zu kurz)"""
        detector = ArtifactDetector()
        artifacts = detector.detect(INLINE_CODE)
        assert len(artifacts) == 0

    def test_short_code_below_threshold(self):
        """G: Code-Block mit <5 Zeilen T: Kein Artifact"""
        detector = ArtifactDetector()
        artifacts = detector.detect(SHORT_CODE)
        assert len(artifacts) == 0


# ── Test Suite 2: Artifact-Metadaten ─────────────────────────────────────────

class TestArtifactMetadata:

    def test_artifact_has_title(self):
        """G: Python-Block T: Artifact hat automatisch generierten Titel"""
        artifacts = ArtifactDetector().detect(PYTHON_BLOCK)
        assert artifacts[0].title
        assert isinstance(artifacts[0].title, str)

    def test_artifact_has_content(self):
        """G: Python-Block T: Artifact.content enthält den Code ohne ```-Fences"""
        artifacts = ArtifactDetector().detect(PYTHON_BLOCK)
        content = artifacts[0].content
        assert '```' not in content
        assert 'def list_files' in content

    def test_artifact_has_language(self):
        """G: ```python Block T: artifact.language == 'python'"""
        artifacts = ArtifactDetector().detect(PYTHON_BLOCK)
        assert artifacts[0].language == 'python'

    def test_chat_text_without_code_preserved(self):
        """G: Antwort mit Text + Code T: text_parts enthält nur den Non-Code-Text"""
        artifacts = ArtifactDetector().detect(PYTHON_BLOCK)
        text = ArtifactDetector().extract_text(PYTHON_BLOCK)
        assert 'Ein Beispielskript:' in text
        assert 'Das war alles.' in text
        assert 'def list_files' not in text


# ── Test Suite 3: Markdown-Ersatz im Chat-Text ────────────────────────────────

class TestChatTextReplacement:

    def test_code_block_replaced_with_placeholder(self):
        """G: Text mit Code-Block T: extract_text() gibt Placeholder zurück statt Code"""
        text = ArtifactDetector().extract_text(PYTHON_BLOCK)
        assert '[📄 Artifact:' in text or 'script' in text.lower() or 'artifact' in text.lower()
        assert 'def list_files' not in text

    def test_text_only_response_unchanged(self):
        """G: Antwort ohne Code-Block T: extract_text() gibt original zurück"""
        plain = "Das ist eine normale Antwort ohne Code."
        text = ArtifactDetector().extract_text(plain)
        assert text == plain
