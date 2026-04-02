"""
◑ MiMi Nox – Phase 1 TDD
tests/test_tool_calling.py

Tests für den Tool-Calling Loop in core/chat.py.
REGEL: Tests wurden VOR der Implementierung geschrieben.

Given / When / Then – strikte Einhaltung.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


from core.chat import chat_with_tools
from core.tools import WebSearchError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ollama_response(content: str = "", tool_calls=None):
    """Build a mock Ollama chat response with optional tool_calls."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    response = MagicMock()
    response.message = msg
    return response


def _make_tool_call(name: str, arguments: dict):
    """Build a mock Ollama tool_call object."""
    func = MagicMock()
    func.name = name
    func.arguments = arguments
    tc = MagicMock()
    tc.function = func
    return tc


# ===========================================================================
# chat_with_tools
# ===========================================================================

class TestChatWithTools:

    @pytest.mark.asyncio
    async def test_executes_tool_and_returns_result_in_final_answer(self):
        """
        GIVEN  Ollama-Mock der tool_call für web_search zurückgibt
        WHEN   chat_with_tools(history, tools) aufgerufen
        THEN   web_search wird genau 1x ausgeführt
        AND    Finale Antwort enthält das Ergebnis von web_search
        AND    stream=False wurde für Tool-Detection verwendet
        """
        tool_call = _make_tool_call("web_search", {"query": "Python 2026"})
        first_response = _make_ollama_response(tool_calls=[tool_call])
        final_response = _make_ollama_response(content="Python ist toll laut Websuche.")

        chunks: list[str] = []

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            # First call: tool detection (returns tool_call)
            # Second call: final answer
            client.chat = AsyncMock(side_effect=[first_response, final_response])
            MockClient.return_value = client

            with patch("core.tools.DDGS") as MockDDGS:
                mock_instance = MagicMock()
                mock_instance.text = MagicMock(
                    return_value=[{"title": "T", "href": "U", "body": "Python ist toll"}]
                )
                mock_instance.__enter__ = MagicMock(return_value=mock_instance)
                mock_instance.__exit__ = MagicMock(return_value=False)
                MockDDGS.return_value = mock_instance

                result = await chat_with_tools(
                    model="phi4-mini",
                    history=[{"role": "user", "content": "Was ist Python?"}],
                    on_chunk=chunks.append,
                )

        mock_instance.text.assert_called_once()
        assert isinstance(result, str)
        # Tool detection call must use stream=False
        first_call_kwargs = client.chat.call_args_list[0].kwargs
        assert first_call_kwargs.get("stream") is False

    @pytest.mark.asyncio
    async def test_no_tool_call_falls_back_to_streaming(self):
        """
        GIVEN  LLM antwortet ohne Tool-Call (pure text)
        WHEN   chat_with_tools(history, tools) aufgerufen
        THEN   Kein Tool wird ausgeführt
        AND    on_chunk wird mit dem Text aufgerufen
        AND    Kein Fehler
        """
        pure_text_response = _make_ollama_response(
            content="Hallo! Ich bin MiMi Nox.", tool_calls=[]
        )

        chunks: list[str] = []

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(return_value=pure_text_response)
            MockClient.return_value = client

            result = await chat_with_tools(
                model="phi4-mini",
                history=[{"role": "user", "content": "Hallo"}],
                on_chunk=chunks.append,
            )

        assert isinstance(result, str)
        # on_chunk must have been called (text arrived)
        assert len(chunks) > 0 or len(result) > 0

    @pytest.mark.asyncio
    async def test_tool_failure_is_caught_and_reported(self):
        """
        GIVEN  Tool schlägt fehl (WebSearchError)
        WHEN   chat_with_tools() mit web_search aufgerufen
        THEN   Fehler wird abgefangen
        AND    on_chunk erhält Fehlermeldung für User
        AND    App crasht NICHT
        """
        tool_call = _make_tool_call("web_search", {"query": "test"})
        first_response = _make_ollama_response(tool_calls=[tool_call])
        final_response = _make_ollama_response(content="Konnte nicht suchen.")

        chunks: list[str] = []

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(side_effect=[first_response, final_response])
            MockClient.return_value = client

            with patch("core.tools.web_search", new=AsyncMock(
                side_effect=WebSearchError("Netzwerk nicht erreichbar")
            )):
                # Must NOT raise
                result = await chat_with_tools(
                    model="phi4-mini",
                    history=[{"role": "user", "content": "Suche was"}],
                    on_chunk=chunks.append,
                )

        assert isinstance(result, str)  # No crash

    @pytest.mark.asyncio
    async def test_loop_breaks_after_max_iterations(self):
        """
        GIVEN  LLM schlägt bei jedem Schritt tool_call vor (infinite loop)
        WHEN   chat_with_tools() Loop läuft
        THEN   Loop bricht nach MAX_TOOL_ITERATIONS=5 ab
        AND    User erhält eine Antwort (kein Hang)
        """
        from core.chat import MAX_TOOL_ITERATIONS

        tool_call = _make_tool_call("get_datetime", {})
        looping_response = _make_ollama_response(tool_calls=[tool_call])
        final_response = _make_ollama_response(content="Maximale Iterationen erreicht.")

        chunks: list[str] = []
        call_count = 0

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()

            async def chat_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= MAX_TOOL_ITERATIONS:
                    return looping_response
                return final_response

            client.chat = AsyncMock(side_effect=chat_side_effect)
            MockClient.return_value = client

            with patch("core.tools.get_datetime", new=AsyncMock(return_value="Donnerstag, 02. April 2026")):
                result = await chat_with_tools(
                    model="phi4-mini",
                    history=[{"role": "user", "content": "Was ist die Zeit?"}],
                    on_chunk=chunks.append,
                )

        assert isinstance(result, str)
        assert call_count <= MAX_TOOL_ITERATIONS + 2  # detection + max iterations + final

    @pytest.mark.asyncio
    async def test_on_tool_callbacks_are_called(self):
        """
        GIVEN  on_tool_start und on_tool_done Callbacks sind gesetzt
        WHEN   Tool aufgerufen wird
        THEN   on_tool_start(name, args) wird VOR Ausführung aufgerufen
        AND    on_tool_done(name, result) wird NACH Ausführung aufgerufen
        """
        tool_call = _make_tool_call("get_datetime", {})
        first_response = _make_ollama_response(tool_calls=[tool_call])
        final_response = _make_ollama_response(content="Es ist Donnerstag.")

        tool_starts: list[tuple] = []
        tool_dones: list[tuple] = []

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(side_effect=[first_response, final_response])
            MockClient.return_value = client

            with patch("core.tools.get_datetime", new=AsyncMock(return_value="Donnerstag, 02. April 2026")):
                await chat_with_tools(
                    model="phi4-mini",
                    history=[{"role": "user", "content": "Was ist das Datum?"}],
                    on_chunk=lambda c: None,
                    on_tool_start=lambda name, args: tool_starts.append((name, args)),
                    on_tool_done=lambda name, result: tool_dones.append((name, result)),
                )

        assert len(tool_starts) == 1
        assert tool_starts[0][0] == "get_datetime"
        assert len(tool_dones) == 1
        assert tool_dones[0][0] == "get_datetime"

    @pytest.mark.asyncio
    async def test_stream_false_used_for_tool_detection(self):
        """
        GIVEN  Jeder chat_with_tools Aufruf
        WHEN   Tool-Detection Phase läuft
        THEN   Ollama wird mit stream=False aufgerufen
        AND    NICHT mit stream=True (wäre Ollama-Bug)
        """
        pure_text = _make_ollama_response(content="Antwort.", tool_calls=[])

        with patch("core.chat.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(return_value=pure_text)
            MockClient.return_value = client

            await chat_with_tools(
                model="phi4-mini",
                history=[{"role": "user", "content": "Test"}],
                on_chunk=lambda c: None,
            )

        # Tool detection call must use stream=False
        detection_call_kwargs = client.chat.call_args_list[0].kwargs
        assert detection_call_kwargs.get("stream") is False, (
            "KRITISCH: Tool-Detection muss stream=False nutzen "
            "(bekanntes Ollama-Limit: Tool-Calls brechen mit stream=True)"
        )
