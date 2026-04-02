"""
◑ MiMi Nox – Phase 3 TDD
tests/test_react.py

REGEL: Tests VOR Implementierung. ROT zuerst, dann GRÜN.
Given / When / Then – strikt.

ReAct = Reason + Act + Observe + Reflect
Reflexion = Selbst-Kritik + Revision wenn Antwort unzureichend
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.react import (
    ReActStep,
    ReflexionResult,
    reflect,
    react_loop,
)


# ---------------------------------------------------------------------------
# Hilfsdaten
# ---------------------------------------------------------------------------

GOOD_ANSWER = (
    "Ollama ist ein Open-Source-Tool zum lokalen Ausführen von LLMs. "
    "Es läuft vollständig offline auf deinem Computer."
)

BAD_ANSWER = "Ich weiß es nicht."

QUESTION = "Was ist Ollama?"


# ---------------------------------------------------------------------------
# Tests: reflect()
# ---------------------------------------------------------------------------

class TestReflect:

    @pytest.mark.asyncio
    async def test_good_answer_needs_no_revision(self):
        """
        GIVEN  Vollständige, korrekte Antwort auf eine Frage
        WHEN   reflect(response=GOOD_ANSWER, question=QUESTION, model=...) aufgerufen
        THEN   Rückgabe: needs_revision=False
        AND    reason ist String (kann leer sein)
        AND    Kein Crash
        """
        with patch("core.react.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Die Antwort ist vollständig und korrekt. REVISION: NEIN")
            ))
            MockClient.return_value = client

            result = await reflect(
                response=GOOD_ANSWER,
                question=QUESTION,
                model="phi4-mini",
            )

        assert isinstance(result, ReflexionResult)
        assert result.needs_revision is False
        assert isinstance(result.reason, str)

    @pytest.mark.asyncio
    async def test_bad_answer_triggers_revision(self):
        """
        GIVEN  Unvollständige Antwort "Ich weiß es nicht."
        WHEN   reflect(response=BAD_ANSWER, question=QUESTION, model=...) aufgerufen
        THEN   Rückgabe: needs_revision=True
        AND    reason enthält Begründung (nicht-leerer String)
        """
        with patch("core.react.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(
                    content="Die Antwort ist unvollständig. REVISION: JA\nGrund: Keine konkreten Informationen."
                )
            ))
            MockClient.return_value = client

            result = await reflect(
                response=BAD_ANSWER,
                question=QUESTION,
                model="phi4-mini",
            )

        assert isinstance(result, ReflexionResult)
        assert result.needs_revision is True
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0

    @pytest.mark.asyncio
    async def test_reflect_returns_reflexion_result_always(self):
        """
        GIVEN  Ollama gibt unerwartete Antwort zurück (kein REVISION: JA/NEIN)
        WHEN   reflect() aufgerufen
        THEN   Rückgabe ist ReflexionResult (kein Crash)
        AND    needs_revision ist bool
        """
        with patch("core.react.ollama.AsyncClient") as MockClient:
            client = AsyncMock()
            client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Ich bin ein Sprachmodell.")
            ))
            MockClient.return_value = client

            result = await reflect(
                response="Test-Antwort",
                question="Test-Frage",
                model="phi4-mini",
            )

        assert isinstance(result, ReflexionResult)
        assert isinstance(result.needs_revision, bool)


# ---------------------------------------------------------------------------
# Tests: react_loop()
# ---------------------------------------------------------------------------

class TestReactLoop:

    @pytest.mark.asyncio
    async def test_simple_question_terminates(self):
        """
        GIVEN  Einfache Frage die kein Tool braucht (mock: direkte Antwort)
        WHEN   react_loop(question, model=...) ausgeführt
        THEN   Gibt nicht-leeren String zurück
        AND    Kein Crash
        AND    Terminiert in ≤5 Iterationen
        """
        steps_recorded: list[ReActStep] = []

        with patch("core.react.chat_with_tools", new=AsyncMock(
            return_value=GOOD_ANSWER
        )):
            with patch("core.react.reflect", new=AsyncMock(
                return_value=ReflexionResult(needs_revision=False, reason="")
            )):
                result = await react_loop(
                    question=QUESTION,
                    model="phi4-mini",
                    on_step=steps_recorded.append,
                )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_revision_triggered_once_on_bad_answer(self):
        """
        GIVEN  Erste Antwort ist unvollständig (reflect: needs_revision=True)
        AND    Zweite Antwort ist gut (reflect: needs_revision=False)
        WHEN   react_loop() ausgeführt
        THEN   Genau 2 chat_with_tools Aufrufe (original + revision)
        AND    Finale Antwort ist der verbesserte Text
        AND    Maximal 1 Revision (kein infinite loop)
        """
        call_count = [0]

        async def mock_chat(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return BAD_ANSWER
            return GOOD_ANSWER

        revision_count = [0]

        async def mock_reflect(response, question, model):
            revision_count[0] += 1
            if revision_count[0] == 1:
                return ReflexionResult(needs_revision=True, reason="Unvollständig")
            return ReflexionResult(needs_revision=False, reason="")

        with patch("core.react.chat_with_tools", new=mock_chat):
            with patch("core.react.reflect", new=mock_reflect):
                result = await react_loop(
                    question=QUESTION,
                    model="phi4-mini",
                )

        assert call_count[0] == 2
        assert result == GOOD_ANSWER

    @pytest.mark.asyncio
    async def test_max_revisions_respected(self):
        """
        GIVEN  reflect() gibt needs_revision=True bei JEDEM Aufruf zurück
        WHEN   react_loop() ausgeführt
        THEN   Loop bricht nach MAX_REVISIONS (=2) ab
        AND    Kein Crash, gibt trotzdem eine Antwort zurück
        """
        with patch("core.react.chat_with_tools", new=AsyncMock(
            return_value=BAD_ANSWER
        )):
            with patch("core.react.reflect", new=AsyncMock(
                return_value=ReflexionResult(needs_revision=True, reason="Immer schlecht")
            )):
                result = await react_loop(
                    question=QUESTION,
                    model="phi4-mini",
                )

        assert isinstance(result, str)
        assert len(result) > 0  # Gibt last_response zurück, kein Crash

    @pytest.mark.asyncio
    async def test_on_step_callback_called(self):
        """
        GIVEN  react_loop mit on_step Callback
        WHEN   Loop ausgeführt
        THEN   on_step wird mindestens 1x aufgerufen
        AND    Jeder Aufruf übergibt ein ReActStep Objekt
        """
        steps: list[ReActStep] = []

        with patch("core.react.chat_with_tools", new=AsyncMock(
            return_value=GOOD_ANSWER
        )):
            with patch("core.react.reflect", new=AsyncMock(
                return_value=ReflexionResult(needs_revision=False, reason="")
            )):
                await react_loop(
                    question=QUESTION,
                    model="phi4-mini",
                    on_step=steps.append,
                )

        assert len(steps) >= 1
        for step in steps:
            assert isinstance(step, ReActStep)

    @pytest.mark.asyncio
    async def test_react_step_has_required_fields(self):
        """
        GIVEN  Eine Iteration des react_loop
        WHEN   on_step Callback aufgerufen
        THEN   ReActStep hat: iteration, answer, reflexion
        AND    iteration ist int ≥ 1
        """
        steps: list[ReActStep] = []

        with patch("core.react.chat_with_tools", new=AsyncMock(
            return_value=GOOD_ANSWER
        )):
            with patch("core.react.reflect", new=AsyncMock(
                return_value=ReflexionResult(needs_revision=False, reason="")
            )):
                await react_loop(
                    question=QUESTION,
                    model="phi4-mini",
                    on_step=steps.append,
                )

        step = steps[0]
        assert hasattr(step, "iteration")
        assert hasattr(step, "answer")
        assert hasattr(step, "reflexion")
        assert isinstance(step.iteration, int)
        assert step.iteration >= 1
