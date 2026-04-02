"""
◑ MiMi Nox – App

Main Textual application for MiMi Nox (TUI backend).
Branding: ◑ MiMi Nox · Privat. Lokal. Yours.
MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header

from core import __edition__, __tagline__, __version__
from core.chat import (
    OllamaModelNotFoundError,
    OllamaNotReachableError,
    check_ollama_connection,
    send_message_safe,
)
from core.swarm import run_swarm
from core.commands import extract_swarm_task, is_swarm_command, resolve_command
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

    CSS_PATH = Path(__file__).parent / "mimi_nox.tcss"

    TITLE = f"◑ MiMi Nox  v{__version__}"
    SUB_TITLE = __tagline__

    BINDINGS = [
        Binding("ctrl+r", "reset_session", "Reset session", show=True),
        Binding("ctrl+l", "clear_chat", "Clear display", show=True),
        Binding("q", "quit", "Quit", show=True, priority=False),
    ]

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self, model: str = "phi4-mini", reset: bool = False) -> None:
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

        # Check Ollama connection asynchronously (non-blocking)
        self.run_worker(self._async_check_connection(), exclusive=False)

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
                    f"◑ MiMi Nox – Willkommen zurück.\n"
                    f"   Letzte Session: {count} Nachrichten, {when}\n"
                    f"   Ctrl+R = Reset  ·  Ctrl+L = Clear  ·  q = Quit",
                    style="welcome",
                )
            )
        else:
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"◑ MiMi Nox – Bereit. Privat. Lokal. Yours.\n"
                    f"   /post  /debug  /idea  /explain  /commit  /swarm\n"
                    f"   Tab = Autocomplete  ·  ↑↓ = History  ·  q = Quit",
                    style="welcome",
                )
            )

    async def _async_check_connection(self) -> None:
        """Ping Ollama on startup, show model list if model not found."""
        connected, status_text, available = await check_ollama_connection(self.model)

        self.query_one(StatusBar).post_message(
            StatusBar.SetStatus(connected=connected, model=self.model)
        )

        chat = self.query_one(ChatView)

        if not connected:
            chat.post_message(
                ChatView.AddSystemMessage(
                    "⚠  Ollama nicht erreichbar.\n"
                    "   Starte Ollama mit:  ollama serve\n"
                    "   Download:           https://ollama.com",
                    style="error-msg",
                )
            )
            return

        # Model not pulled locally → show available options
        model_present = any(self.model in name for name in available)
        if not model_present:
            model_list = "\n".join(
                f"   • {name}" for name in available[:10]
            ) or "   (keine Modelle installiert)"
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Modell '{self.model}' nicht lokal vorhanden.\n\n"
                    f"   Installiere es mit:\n"
                    f"   ollama pull {self.model}\n\n"
                    f"   Oder starte mit einem vorhandenen Modell:\n"
                    f"{model_list}\n\n"
                    f"   Tipp: ollama pull gemma4:e4b  (★ neu, Tool-Calling, 3GB)",
                    style="error-msg",
                )
            )

    # ── Message Handling ──────────────────────────────────────────────────────

    def on_history_input_submitted(self, event: HistoryInput.Submitted) -> None:
        """User pressed Enter in the HistoryInput widget."""
        user_input = event.value.strip()
        if not user_input:
            return

        # /swarm → multi-agent pipeline (bypass normal chat)
        if is_swarm_command(user_input):
            task = extract_swarm_task(user_input)
            if not task:
                self.query_one(ChatView).post_message(
                    ChatView.AddSystemMessage(
                        "Usage: /swarm <Aufgabe>\n"
                        "Beispiel: /swarm Erstelle eine REST API für ein Buchungssystem",
                        style="system-msg",
                    )
                )
                return
            self.query_one(ChatView).post_message(ChatView.AddUserMessage(user_input))
            self._run_swarm(task)
            return

        # Normal chat: resolve slash commands before sending
        resolved = resolve_command(user_input)

        # Add user message to session
        self._session.append(Message(role="user", content=resolved))

        # Show original input in UI
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

        def on_loading_hint() -> None:
            """Called when model takes >15s to produce first token (loading from disk)."""
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⏳ Modell '{self.model}' wird gerade geladen…\n"
                    f"   Große Modelle (>4GB) brauchen beim ersten Aufruf 30-90s.\n"
                    f"   Bitte warten.",
                    style="fallback-hint",
                )
            )

        def on_fallback() -> None:
            chat.post_message(
                ChatView.AddSystemMessage(
                    "↻ Streaming fehlgeschlagen, versuche ohne Stream…",
                    style="fallback-hint",
                )
            )

        try:
            # Wrap in loading-hint task: if first token takes > 15s, show hint
            hint_task = asyncio.create_task(
                self._loading_hint_after_delay(on_loading_hint, delay=15.0)
            )

            try:
                full_response = await send_message_safe(
                    model=self.model,
                    history=self._session,
                    on_chunk=on_chunk,
                    on_fallback=on_fallback,
                    on_loading_hint=on_loading_hint,
                )
            finally:
                hint_task.cancel()
                try:
                    await hint_task
                except asyncio.CancelledError:
                    pass

        except OllamaNotReachableError:
            status.post_message(
                StatusBar.SetError(
                    "Ollama nicht erreichbar – starte mit: ollama serve"
                )
            )
            # Remove the user message we added optimistically
            if self._session and self._session[-1]["role"] == "user":
                self._session.pop()
            chat.post_message(
                ChatView.AddSystemMessage(
                    "⚠  Ollama nicht erreichbar.  Starte mit:  ollama serve",
                    style="error-msg",
                )
            )
        except OllamaModelNotFoundError as exc:
            status.post_message(StatusBar.SetError(f"Modell nicht gefunden: {exc.model}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Modell '{exc.model}' nicht vorhanden.\n"
                    f"   Installiere es mit:  ollama pull {exc.model}",
                    style="error-msg",
                )
            )
        except asyncio.CancelledError:
            # Worker was cancelled (e.g., app is closing) – clean exit
            pass
        except Exception as exc:
            # Unknown error – show in UI, never crash
            status.post_message(StatusBar.SetError(f"Fehler: {exc}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Unerwarteter Fehler: {exc}",
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

    @staticmethod
    async def _loading_hint_after_delay(
        callback: Callable[[], None], delay: float
    ) -> None:
        """Helper: call callback after delay seconds (cancelled if model responds first)."""
        await asyncio.sleep(delay)
        callback()

    # ── Swarm Worker ──────────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _run_swarm(self, task: str) -> None:
        """
        Multi-agent swarm pipeline:
          Planer → N Spezialisten (parallel) → Synthesizer → ChatView

        The exclusive=True means only one AI job (chat OR swarm) runs at a time.
        """
        chat = self.query_one(ChatView)
        status = self.query_one(StatusBar)
        hist_input = self.query_one(HistoryInput)

        hist_input.disable()
        status.post_message(StatusBar.SetStreaming(True))
        chat.post_message(ChatView.BeginAssistantMessage())

        accumulated = ""

        def on_progress(text: str) -> None:
            nonlocal accumulated
            accumulated += text + "\n"
            # Stream progress into the live assistant area
            chat.post_message(ChatView.AppendChunk(text + "\n"))

        try:
            result = await run_swarm(
                task=task,
                model=self.model,
                on_progress=on_progress,
            )

            # Show final synthesis as the main response
            final_text = (
                "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🌲 Swarm-Ergebnis\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                + result.final
            )
            chat.post_message(ChatView.AppendChunk(final_text))

            # Persist to session
            self._session.append(Message(role="user", content=f"/swarm {task}"))
            self._session.append(
                Message(role="assistant", content=accumulated + final_text)
            )
            save_session(self._session)

        except OllamaNotReachableError:
            status.post_message(StatusBar.SetError("Ollama nicht erreichbar"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    "⚠  Swarm abgebrochen: Ollama nicht erreichbar.",
                    style="error-msg",
                )
            )
        except OllamaModelNotFoundError as exc:
            status.post_message(StatusBar.SetError(f"Modell fehlt: {exc.model}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Modell '{exc.model}' nicht vorhanden.\n"
                    f"   ollama pull {exc.model}",
                    style="error-msg",
                )
            )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            status.post_message(StatusBar.SetError(f"Swarm-Fehler: {exc}"))
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⚠  Swarm-Fehler: {exc}",
                    style="error-msg",
                )
            )
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
                "◑ Session zurückgesetzt. Frischer Start.",
                style="system-msg",
            )
        )

    def action_clear_chat(self) -> None:
        """Ctrl+L – clear the visual display only. Session data kept."""
        self.query_one(ChatView).clear_display()

    def action_quit(self) -> None:
        """q – quit ClawDash."""
        self.exit()
