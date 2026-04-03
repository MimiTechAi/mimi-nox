"""
◑ MiMi Nox – Thinking Stream Parser Tests
tests/test_thinking.py

TDD Tests für den Gemma4 E4B <|think|> Modus.
When/Given/Then Spezifikationen.
"""
from __future__ import annotations

import pytest

from core.chat import ThinkingStreamParser, THINK_OPEN, THINK_CLOSE


# ---------------------------------------------------------------------------
# ThinkingStreamParser Unit Tests
# ---------------------------------------------------------------------------

class TestThinkingParser:
    """Parsing von Gemma4 <|think|> Tags."""

    def test_GIVEN_stream_with_thinking_WHEN_parsed_THEN_separates_thought_from_answer(self):
        """
        GIVEN ein Stream-Output mit <|think|>Ich überlege...<|/think|>Finale Antwort
        WHEN  ThinkingStreamParser den Output verarbeitet
        THEN  thinking="Ich überlege...", answer="Finale Antwort"
        """
        chunks: list[str] = []
        thinking: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=lambda t: thinking.append(t),
        )

        parser.feed(f"{THINK_OPEN}Ich überlege...{THINK_CLOSE}Finale Antwort")
        parser.flush()

        assert "".join(thinking) == "Ich überlege..."
        assert "".join(chunks) == "Finale Antwort"
        assert parser.answer == "Finale Antwort"
        assert parser.thinking == "Ich überlege..."

    def test_GIVEN_stream_without_thinking_WHEN_parsed_THEN_returns_full_as_answer(self):
        """
        GIVEN ein Stream-Output ohne Thinking-Tags
        WHEN  ThinkingStreamParser den Output verarbeitet
        THEN  thinking="", answer=gesamter Output
        """
        chunks: list[str] = []
        thinking: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=lambda t: thinking.append(t),
        )

        parser.feed("Hallo, ich bin Nox!")
        parser.flush()

        assert "".join(chunks) == "Hallo, ich bin Nox!"
        assert "".join(thinking) == ""
        assert parser.answer == "Hallo, ich bin Nox!"
        assert parser.thinking == ""

    def test_GIVEN_partial_thinking_tag_WHEN_streaming_chunk_by_chunk_THEN_buffers_correctly(self):
        """
        GIVEN Thinking-Tags die über mehrere Chunks gesplittet sind
        WHEN  Chunks einzeln verarbeitet werden
        THEN  Tag-Übergänge werden korrekt erkannt
        """
        chunks: list[str] = []
        thinking: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=lambda t: thinking.append(t),
        )

        # Simuliere Wort-für-Wort Streaming
        tokens = [
            "<|", "think", "|>",           # Open tag gesplittet
            "Denke ", "nach...",            # Thinking content
            "<|/", "think", "|>",          # Close tag gesplittet
            "Die ", "Antwort ", "ist 42.",  # Answer content
        ]

        for token in tokens:
            parser.feed(token)
        parser.flush()

        full_thought = "".join(thinking)
        full_answer = "".join(chunks)

        assert "Denke " in full_thought
        assert "nach..." in full_thought
        assert "42" in full_answer
        # Keine Thinking-Tags in der Antwort!
        assert THINK_OPEN not in full_answer
        assert THINK_CLOSE not in full_answer

    def test_GIVEN_no_thinking_callback_WHEN_thinking_tags_present_THEN_strips_tags_silently(self):
        """
        GIVEN on_thinking=None (kein Callback)
        WHEN  Thinking-Tags im Stream sind
        THEN  Tags werden still entfernt, nur Antwort kommt durch
        """
        chunks: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=None,
        )

        parser.feed(f"{THINK_OPEN}Internes Denken{THINK_CLOSE}Sichtbare Antwort")
        parser.flush()

        assert "".join(chunks) == "Sichtbare Antwort"
        assert parser.thinking == "Internes Denken"
        assert parser.answer == "Sichtbare Antwort"

    def test_GIVEN_multiple_thinking_blocks_WHEN_parsed_THEN_all_collected(self):
        """
        GIVEN Stream mit mehreren Thinking-Blöcken
        WHEN  geparst
        THEN  alle Thinking-Blöcke werden gesammelt
        """
        chunks: list[str] = []
        thinking: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=lambda t: thinking.append(t),
        )

        text = (
            f"Intro {THINK_OPEN}Gedanke 1{THINK_CLOSE}"
            f"Mitte {THINK_OPEN}Gedanke 2{THINK_CLOSE}"
            f"Ende"
        )
        parser.feed(text)
        parser.flush()

        assert "Gedanke 1" in "".join(thinking)
        assert "Gedanke 2" in "".join(thinking)
        assert "Intro " in "".join(chunks)
        assert "Mitte " in "".join(chunks)
        assert "Ende" in "".join(chunks)

    def test_GIVEN_empty_thinking_block_WHEN_parsed_THEN_no_crash(self):
        """
        GIVEN leerer Thinking-Block: <|think|><|/think|>
        WHEN  geparst
        THEN  kein Crash, thinking=""
        """
        chunks: list[str] = []

        parser = ThinkingStreamParser(
            on_chunk=lambda c: chunks.append(c),
            on_thinking=lambda _: None,
        )

        parser.feed(f"{THINK_OPEN}{THINK_CLOSE}Antwort")
        parser.flush()

        assert parser.thinking == ""
        assert parser.answer == "Antwort"
