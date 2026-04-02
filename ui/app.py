"""
ClawDash App – BlackForest Edition

Main Textual application. Orchestrates:
- Layout: Header / ChatView / HistoryInput / StatusBar
- Worker: @work(exclusive=True) for Ollama streaming
- Session: load on start, save after every message
- Keyboard: Ctrl+R (reset), Ctrl+L (clear), q (quit)

Design rules enforced here:
- Workers communicate with UI ONLY via post_message()
- Input is disabled during streaming (Input.disabled)
- Never crash – all errors caught and shown in StatusBar
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header

from core import __edition__, __version__
from core.chat import (
    OllamaModelNotFoundError,
    OllamaNotReachableError,
    check_ollama_connection,
    send_message_safe,
)
from core.commands import resolve_command
from core.session import (
    delete_session,
    load_last_session,
    save_session,
    session_info,
    was_session_corrupt,
)
from core.types import Message
from ui.widgets import ChatView, HistoryInput, StatusBar


class ClawDashApp(App):
    """
    ClawDash – BlackForest Edition

    keyboard-first TUI for local LLMs via Ollama.
    MiMi Tech AI UG – Bad Liebenzell, Schwarzwald.
    """

    # Path is relative to this file's location
    CSS_PATH = Path(__file__).parent / "clawdash.tcss"

    TITLE = f"🌲 ClawDash  {__edition__}  v{__version__}"
    SUB_TITLE = ""

    BINDINGS = [
        Binding("ctrl+r", "reset_session", "Reset session", show=True),
        Binding("ctrl+l", "clear_chat", "Clear display", show=True),
        Binding("q", "quit", "Quit", show=True, priority=False),
    ]

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self, model: str = "llama3.2", reset: bool = False) -> None:
        super().__init__()
        self.model = model
        self._reset_on_start = reset
        self._session: list[Message] = []

    # ── Layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ChatView(id="chat-view")
        yield HistoryInput(id="input-area")
        yield StatusBar(id="status-bar")

    # ── Startup ──────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Called when the app is ready. Load session and connect to Ollama."""
        if self._reset_on_start:
            delete_session()

        self._load_session_and_greet()
        self.query_one(HistoryInput).focus_input()

        # Check Ollama connection asynchronously
        self._check_connection()

    def _load_session_and_greet(self) -> None:
        chat = self.query_one(ChatView)

        if was_session_corrupt():
            chat.post_message(
                ChatView.AddSystemMessage(
                    "[Session was corrupt – starting fresh]",
                    style="error-msg",
                )
            )

        session = load_last_session()
        self._session = session
        count, when = session_info()

        if count > 0:
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"🌲 ClawDash {__edition__} — Welcome back. "
                    f"Last session restored ({count} messages, {when}).\n"
                    f"   Ctrl+R to reset · q to quit",
                    style="welcome",
                )
            )
        else:
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"🌲 ClawDash {__edition__} — No previous session.\n"
                    f"   Try /post, /debug, /idea, /explain, /commit\n"
                    f"   Ctrl+R to reset · q to quit",
                    style="welcome",
                )
            )

    def _check_connection(self) -> None:
        """Non-blocking Ollama ping on startup."""
        self._run_connection_check()

    def _run_connection_check(self) -> None:
        """Use Textual's run_worker to async-ping Ollama without blocking the UI."""
        self.run_worker(self._async_check_connection(), exclusive=False)

    async def _async_check_connection(self) -> None:
        connected, status_text = await check_ollama_connection(self.model)
        status_bar = self.query_one(StatusBar)
        status_bar.post_message(
            StatusBar.SetStatus(connected=connected, model=self.model)
        )
        if not connected:
            self.query_one(ChatView).post_message(
                ChatView.AddSystemMessage(
                    "⚠  Ollama not running. Start it with:  ollama serve",
                    style="error-msg",
                )
            )

    # ── Message Handling ──────────────────────────────────────────────────────

    def on_history_input_submitted(self, event: HistoryInput.Submitted) -> None:
        """User pressed Enter in the HistoryInput widget."""
        user_input = event.value.strip()
        if not user_input:
            return

        # Resolve slash commands before sending
        resolved = resolve_command(user_input)

        # Add user message to session
        self._session.append(Message(role="user", content=resolved))

        # Show original input in UI (not the resolved prompt – avoids noise)
        chat = self.query_one(ChatView)
        chat.post_message(ChatView.AddUserMessage(user_input))

        # Kick off the streaming worker
        self._stream_response()

    # ── Streaming Worker ──────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _stream_response(self) -> None:
        """
        Async Textual worker. Streams Ollama response token by token.

        CRITICAL design rules:
        - Never modify widgets directly. Use post_message() only.
        - asyncio.CancelledError must propagate (don't swallow it).
        - Input is disabled for the duration of streaming.
        """
        chat = self.query_one(ChatView)
        status = self.query_one(StatusBar)
        hist_input = self.query_one(HistoryInput)

        hist_input.disable()
        status.post_message(StatusBar.SetStreaming(True))
        chat.post_message(ChatView.BeginAssistantMessage())

        full_response = ""

        def on_chunk(chunk: str) -> None:
            nonlocal full_response
            full_response += chunk
            chat.post_message(ChatView.AppendChunk(chunk))

        def on_fallback() -> None:
            chat.post_message(
                ChatView.AddSystemMessage(
                    "↻ Streaming failed, retrying without stream…",
                    style="fallback-hint",
                )
            )

        try:
            full_response = await send_message_safe(
                model=self.model,
                history=self._session,
                on_chunk=on_chunk,
                on_fallback=on_fallback,
            )
        except OllamaNotReachableError:
            status.post_message(
                StatusBar.SetError(
                    "Ollama not running. Start with: ollama serve"
                )
            )
            # Remove the user message we added optimistically
            if self._session and self._session[-1]["role"] == "user":
                self._session.pop()
            chat.post_message(
                ChatView.AddSystemMessage(
                    "⚠  Ollama not running. Start with:  ollama serve",
                    style="error-msg",
                )
            )
        except OllamaModelNotFoundError as exc:
            status.post_message(StatusBar.SetError(f"Model not found: {exc.model}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Model '{exc.model}' not found. Run:  ollama pull {exc.model}",
                    style="error-msg",
                )
            )
        except asyncio.CancelledError:
            # Worker was cancelled (e.g., app is closing) – clean exit
            pass
        except Exception as exc:
            # Unknown error – show in UI, never crash
            status.post_message(StatusBar.SetError(f"Error: {exc}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Unexpected error: {exc}",
                    style="error-msg",
                )
            )
        else:
            # Success – persist assistant message
            if full_response:
                self._session.append(
                    Message(role="assistant", content=full_response)
                )
                save_session(self._session)
        finally:
            chat.post_message(ChatView.FinalizeAssistantMessage())
            status.post_message(StatusBar.SetStreaming(False))
            hist_input.enable()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_reset_session(self) -> None:
        """Ctrl+R – delete session and clear display."""
        delete_session()
        self._session = []
        chat = self.query_one(ChatView)
        chat.clear_display()
        chat.post_message(
            ChatView.AddSystemMessage(
                "🌲 Session reset. Starting fresh.",
                style="system-msg",
            )
        )

    def action_clear_chat(self) -> None:
        """Ctrl+L – clear the visual display only. Session data kept."""
        self.query_one(ChatView).clear_display()

    def action_quit(self) -> None:
        """q – quit ClawDash."""
        self.exit()
