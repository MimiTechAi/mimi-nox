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
    chat_with_tools,
)
from core.react import react_loop, ReActStep
from core.tools import ShellConfirmationRequired
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
from core.memory import Memory
from core.profile import UserProfile, load_profile
from core.corrections import CorrectionJournal
from core.skills import SkillLoader
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
        # Phase 2: Memory + Skills + Profile (lazy init)
        self._memory: Memory | None = None
        self._profile: UserProfile | None = None
        self._corrections: CorrectionJournal | None = None
        self._skill_loader: SkillLoader | None = None
        # Vollständige History für nächsten _stream_response Call
        # (inkl. Skill-System-Prompt + Profil + Korrekturen)
        self._pending_history: list[Message] = []

    # ── Layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ChatView(id="chat-view")
        yield HistoryInput(id="input-area")
        yield StatusBar(id="status-bar")

    # ── Startup ──────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Called when the app is ready. Load session, init memory, connect to Ollama."""
        if self._reset_on_start:
            delete_session()

        # Lazy init Phase 2 modules (silently – no crash if unavailable)
        try:
            self._memory = Memory()
            self._profile = load_profile()
            self._corrections = CorrectionJournal()
            self._skill_loader = SkillLoader()
        except Exception:
            pass  # Memory unavailable – app still works

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

        # ── Skill-Trigger auswerten (/research, /files, /review, /write, /shell)
        resolved = resolve_command(user_input)
        skill_system_prompt: str | None = None
        if user_input.startswith("/") and self._skill_loader is not None:
            skill = self._skill_loader.resolve_trigger(user_input.split()[0])
            if skill is not None:
                skill_system_prompt = skill.system_prompt
                # Skill-Kontext als erste Nachricht falls Session leer
                self.query_one(ChatView).post_message(
                    ChatView.AddSystemMessage(
                        f"⚡ Skill aktiv: {skill.name}",
                        style="tool-call",
                    )
                )

        # ── Korrektur erkennen ("Das ist falsch:" oder "Das stimmt nicht:")
        correction_keywords = ("das ist falsch", "das stimmt nicht", "falsch:", "nicht korrekt")
        if any(kw in user_input.lower() for kw in correction_keywords):
            if self._corrections is not None:
                self._corrections.add(
                    wrong="(letzte Antwort)",
                    correct=user_input,
                )

        # ── Vollständige History aufbauen (einschließlich Kontext-Schichten)
        pending: list[Message] = []

        # Schicht 1: Profil-Kontext (wenn Profil gefüllt)
        if self._profile is not None:
            ctx = self._profile.to_context_string()
            if ctx:
                pending.append(Message(role="system", content=ctx))

        # Schicht 2: Korrektions-Kontext (vermeidet Fehler-Wiederholung)
        if self._corrections is not None:
            corr_ctx = self._corrections.to_context_string(max_items=3)
            if corr_ctx:
                pending.append(Message(role="system", content=corr_ctx))

        # Schicht 3: Skill-System-Prompt (überschreibt Standard-Verhalten)
        if skill_system_prompt:
            pending.append(Message(role="system", content=skill_system_prompt))

        # Schicht 4: Konversations-History
        pending.extend(self._session)

        # Nutzer-Nachricht hinzufügen
        self._session.append(Message(role="user", content=resolved))
        pending.append(Message(role="user", content=resolved))

        # Für den Worker speichern
        self._pending_history = pending

        # Show in UI
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
            """Wird aufgerufen wenn Modell >15s braucht (Laden von Disk)."""
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"⏳ Modell '{self.model}' wird gerade geladen…\n"
                    f"   Große Modelle (>4GB) brauchen beim ersten Aufruf 30-90s.\n"
                    f"   Bitte warten.",
                    style="fallback-hint",
                )
            )

        try:
            # Hint-Task: zeigt "Laden…" wenn Modell >15s braucht
            hint_task = asyncio.create_task(
                self._loading_hint_after_delay(on_loading_hint, delay=15.0)
            )

            # ── Tool-Call Callbacks ─────────────────────────────────────────
            def on_tool_start(tool_name: str, args: dict) -> None:
                """Zeigt Spinner-Meldung wenn Tool startet."""
                args_preview = ", ".join(
                    f"{k}={str(v)[:40]!r}" for k, v in args.items()
                )
                chat.post_message(
                    ChatView.AddSystemMessage(
                        f"🔍 {tool_name}({args_preview})…",
                        style="tool-call",
                    )
                )

            def on_tool_done(tool_name: str, result: str) -> None:
                """Zeigt Häkchen wenn Tool fertig."""
                preview = result[:80].replace("\n", " ")
                chat.post_message(
                    ChatView.AddSystemMessage(
                        f"✅ {tool_name} → {preview}…" if len(result) > 80 else f"✅ {tool_name} → {result}",
                        style="tool-done",
                    )
                )

            # ── on_step: zeigt Revisions-Hinweis BEVOR neue Antwort kommt
            def on_react_step(step: ReActStep) -> None:
                """Wird VOR dem nächsten LLM-Aufruf aufgerufen (on_step nach reflect)."""
                if step.reflexion.needs_revision:
                    # Hinweis: neue Antwort kommt gleich
                    chat.post_message(
                        ChatView.AddSystemMessage(
                            f"🔄 Reflexion: Antwort unzureichend – wird verbessert…\n"
                            f"   Grund: {step.reflexion.reason[:120]}",
                            style="tool-call",
                        )
                    )

            # Frage sicher aus pending_history extrahieren
            if self._pending_history:
                last_msg = self._pending_history[-1]
                question = last_msg.get("content", "") if isinstance(last_msg, dict) else ""
                context = self._pending_history[:-1]
            else:
                question = ""
                context = []

            try:
                full_response = await react_loop(
                    question=question,
                    model=self.model,
                    context=context,
                    on_chunk=on_chunk,
                    on_tool_start=on_tool_start,
                    on_tool_done=on_tool_done,
                    on_step=on_react_step,
                )
            finally:
                hint_task.cancel()
                try:
                    await hint_task
                except asyncio.CancelledError:
                    pass

        except ShellConfirmationRequired as exc:
            # ── Shell-Bestätigung (TUI Inline-Confirm) ──────────────────────
            chat.post_message(
                ChatView.AddSystemMessage(
                    f"🖥  Shell-Befehl vorgeschlagen:\n"
                    f"   {exc.command}\n\n"
                    f"   Führe ihn manuell aus oder kopiere ihn.",
                    style="tool-call",
                )
            )

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
            # Success – persist assistant + store in memory
            if full_response:
                self._session.append(
                    Message(role="assistant", content=full_response)
                )
                save_session(self._session)
                # Phase 2: wichtige Antworten persistent im Memory speichern
                if self._memory is not None:
                    try:
                        # Letzte User-Frage + Antwort zusammen speichern
                        last_user = next(
                            (m["content"] for m in reversed(self._session)
                             if m["role"] == "user"), ""
                        )
                        self._memory.store(
                            f"Q: {last_user}\nA: {full_response[:500]}",
                            metadata={"model": self.model},
                        )
                    except Exception:
                        pass  # Memory-Fehler crasht nie die App
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
