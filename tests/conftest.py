"""
pytest fixtures shared across all MiMi Nox tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.types import Message


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Redirect MiMi Nox session path to a temporary directory.
    Each test gets a clean, isolated session directory.
    """
    session_dir = tmp_path / ".mimi-nox" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)

    import core.session as session_module

    monkeypatch.setattr(session_module, "SESSION_DIR", session_dir)
    monkeypatch.setattr(
        session_module, "SESSION_FILE", session_dir / "default.json"
    )
    return session_dir


@pytest.fixture
def sample_messages() -> list[Message]:
    return [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
        Message(role="user", content="How are you?"),
        Message(role="assistant", content="I am fine, danke!"),
    ]


# ---------------------------------------------------------------------------
# Ollama mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ollama_chunks() -> list[str]:
    """A realistic list of streaming chunks."""
    return ["Hello", " from", " the", " Black", " Forest", "!"]


@pytest.fixture
def mock_ollama_stream(mock_ollama_chunks: list[str]):
    """AsyncMock that simulates ollama AsyncClient streaming."""

    async def fake_stream(*args, **kwargs):
        for chunk in mock_ollama_chunks:
            yield {"message": {"content": chunk}}

    mock_client = MagicMock()
    mock_client.chat = MagicMock(return_value=fake_stream())
    return mock_client


@pytest.fixture
def mock_ollama_connection_error():
    """Simulates Ollama being unreachable."""
    with patch("ollama.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.chat.side_effect = ConnectionRefusedError(
            "Connection refused – Ollama not running"
        )
        mock_class.return_value = instance
        yield mock_class
