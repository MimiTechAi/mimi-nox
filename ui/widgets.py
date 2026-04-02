"""
ClawDash Widgets – BlackForest Edition

Three focused, reusable Textual widgets:

    HistoryInput  – Input with ↑/↓ history navigation + command completions
    ChatView      – Scrollable chat display with live streaming via Static widget
    StatusBar     – Live status: Ollama connection · model · tagline

Streaming architecture:
    - RichLog holds all COMPLETED messages (user + finalized assistant)
    - Static (#streaming-area) holds the CURRENT streaming assistant response
    - On FinalizeAssistantMessage: flush Static → RichLog, clear Static
    This avoids the RichLog.write(end="") API which doesn't exist.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message as TextualMessage
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

from core.commands import get_completions


# ===========================================================================
# HistoryInput
# ===========================================================================


class HistoryInput(Widget):
    """
    Input widget with ↑/↓ navigation through submission history.

    Also handles:
    - Command mode detection when first character is '/'
    - Tab-completion for slash commands
    - Emitting HistoryInput.Submitted for the App to handle
    """

    DEFAULT_CSS = """
    HistoryInput {
        height: 3;
        layout: vertical;
    }
    """

    class Submitted(TextualMessage):
        """Posted when the user submits (Enter). Contains the raw input value."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    # ── State ────────────────────────────────────────────────────────────────

    _history: list[str]
    _history_index: int  # len(history) = "no history entry active"
    _saved_draft: str    # saves current text when navigating up

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._history = []
        self._history_index = 0
        self._saved_draft = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="command-hint")
        yield Input(
            placeholder="› Type a message or /command…",
            id="chat-input",
        )

    def on_mount(self) -> None:
        self._history_index = 0

    # ── Key handling ─────────────────────────────────────────────────────────

    def on_key(self, event: object) -> None:  # type: ignore[override]
        from textual.events import Key

        if not isinstance(event, Key):
            return

        input_widget = self.query_one("#chat-input", Input)

        if event.key == "up":
            event.prevent_default()
            self._navigate_history(-1, input_widget)

        elif event.key == "down":
            event.prevent_default()
            self._navigate_history(+1, input_widget)

        elif event.key == "tab":
            event.prevent_default()
            self._try_complete(input_widget)

    def _navigate_history(self, direction: int, input_widget: Input) -> None:
        """direction: -1 = older, +1 = newer"""
        if not self._history:
            return

        # Save draft before first upward navigation
        if self._history_index == len(self._history) and direction == -1:
            self._saved_draft = input_widget.value

        new_index = self._history_index + direction
        new_index = max(0, min(len(self._history), new_index))
        self._history_index = new_index

        if new_index == len(self._history):
            input_widget.value = self._saved_draft
        else:
            # new_index counts from the end: 0 = len-1 (newest), 1 = len-2, etc.
            # Pressing UP once → most recent entry (history[-1])
            input_widget.value = self._history[len(self._history) - 1 - new_index]

        # Move cursor to end
        input_widget.cursor_position = len(input_widget.value)

    def _try_complete(self, input_widget: Input) -> None:
        """Tab-complete slash commands."""
        text = input_widget.value
        if not text.startswith("/"):
            return

        # Only complete if it's a single-word prefix (no space yet)
        if " " in text:
            return

        completions = get_completions(text)
        if len(completions) == 1:
            input_widget.value = completions[0] + " "
            input_widget.cursor_position = len(input_widget.value)
        elif len(completions) > 1:
            hint = self.query_one("#command-hint", Static)
            hint.update("  ".join(completions))
            hint.add_class("visible")

    # ── Input change ─────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        hint = self.query_one("#command-hint", Static)
        text = event.value

        if text.startswith("/") and " " not in text:
            completions = get_completions(text)
            if completions:
                hint.update("  ".join(completions))
                hint.add_class("visible")
                self.add_class("command-mode")
                return

        hint.remove_class("visible")
        self.remove_class("command-mode")

    # ── Submission ───────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        # Add to history (avoid duplicates at tip)
        if not self._history or self._history[-1] != value:
            self._history.append(value)

        # Reset index
        self._history_index = len(self._history)
        self._saved_draft = ""

        # Clear input + hint
        event.input.value = ""
        hint = self.query_one("#command-hint", Static)
        hint.remove_class("visible")
        self.remove_class("command-mode")

        # Notify App
        self.post_message(HistoryInput.Submitted(value))

    # ── Public API ────────────────────────────────────────────────────────────

    def disable(self) -> None:
        """Disable input during streaming."""
        self.query_one("#chat-input", Input).disabled = True

    def enable(self) -> None:
        """Re-enable input after streaming."""
        inp = self.query_one("#chat-input", Input)
        inp.disabled = False
        inp.focus()

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()


# ===========================================================================
# ChatView
# ===========================================================================


class ChatView(Widget):
    """
    Scrollable chat display.

    Architecture:
        - RichLog (#chat-log): holds all completed messages
        - Static (#streaming-area): shows the CURRENT streaming response live
          Becomes visible during streaming, cleared+hidden after finalization.

    This avoids the non-existent RichLog.write(end="") API.
    """

    DEFAULT_CSS = """
    ChatView {
        layout: vertical;
        height: 1fr;
    }
    #streaming-area {
        display: none;
        color: #a8c5a0;
        padding: 0 1;
        margin-top: 1;
    }
    #streaming-area.active {
        display: block;
    }
    """

    # ── Textual Messages ─────────────────────────────────────────────────────

    class AddUserMessage(TextualMessage):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class BeginAssistantMessage(TextualMessage):
        """Signals start of a streaming assistant response."""
        pass

    class AppendChunk(TextualMessage):
        def __init__(self, chunk: str) -> None:
            super().__init__()
            self.chunk = chunk

    class FinalizeAssistantMessage(TextualMessage):
        """Streaming complete – flush Static → RichLog."""
        pass

    class AddSystemMessage(TextualMessage):
        def __init__(self, text: str, style: str = "system-msg") -> None:
            super().__init__()
            self.text = text
            self.style = style

    # ── State ────────────────────────────────────────────────────────────────

    _accumulated_chunks: str

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._accumulated_chunks = ""

    def compose(self) -> ComposeResult:
        log = RichLog(id="chat-log", wrap=True, markup=True, highlight=False)
        log.can_focus = False
        yield log
        yield Static("", id="streaming-area", markup=True)

    # ── Message Handlers ─────────────────────────────────────────────────────

    def on_chat_view_add_user_message(self, event: "ChatView.AddUserMessage") -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold #39ff14]You[/bold #39ff14]")
        log.write(f"[#39ff14]{event.text}[/#39ff14]")

    def on_chat_view_begin_assistant_message(
        self, event: "ChatView.BeginAssistantMessage"
    ) -> None:
        self._accumulated_chunks = ""
        streaming = self.query_one("#streaming-area", Static)
        streaming.update("[bold #a8c5a0]Assistant[/bold #a8c5a0]\n▌")
        streaming.add_class("active")

    def on_chat_view_append_chunk(self, event: "ChatView.AppendChunk") -> None:
        self._accumulated_chunks += event.chunk
        streaming = self.query_one("#streaming-area", Static)
        # ▌ cursor at end gives streaming feel
        streaming.update(
            f"[bold #a8c5a0]Assistant[/bold #a8c5a0]\n"
            f"[#a8c5a0]{self._accumulated_chunks}[/#a8c5a0]▌"
        )

    def on_chat_view_finalize_assistant_message(
        self, event: "ChatView.FinalizeAssistantMessage"
    ) -> None:
        # Hide streaming widget
        streaming = self.query_one("#streaming-area", Static)
        streaming.remove_class("active")
        streaming.update("")

        # Flush to RichLog as a permanent entry
        if self._accumulated_chunks:
            log = self.query_one("#chat-log", RichLog)
            log.write(f"\n[bold #a8c5a0]Assistant[/bold #a8c5a0]")
            log.write(f"[#a8c5a0]{self._accumulated_chunks}[/#a8c5a0]")

        self._accumulated_chunks = ""

    def on_chat_view_add_system_message(
        self, event: "ChatView.AddSystemMessage"
    ) -> None:
        log = self.query_one("#chat-log", RichLog)
        style_map = {
            "welcome":       "#5a7a5a italic",
            "system-msg":    "#5a7a5a",
            "error-msg":     "bold #ff6b35",
            "fallback-hint": "#5a7a5a italic",
        }
        rich_style = style_map.get(event.style, "#5a7a5a")
        log.write(f"[{rich_style}]{event.text}[/{rich_style}]")

    # ── Public API ────────────────────────────────────────────────────────────

    def clear_display(self) -> None:
        """Clear the visual display (Ctrl+L). Session data is unaffected."""
        self.query_one("#chat-log", RichLog).clear()
        streaming = self.query_one("#streaming-area", Static)
        streaming.remove_class("active")
        streaming.update("")
        self._accumulated_chunks = ""


# ===========================================================================
# StatusBar
# ===========================================================================


class StatusBar(Widget):
    """
    Single-line status bar docked at the bottom.

    Shows: [●/✗/⏳ Ollama status] │ [model] │ [🌲 tagline]
    """

    # ── Textual Messages ─────────────────────────────────────────────────────

    class SetStatus(TextualMessage):
        def __init__(self, connected: bool, model: str) -> None:
            super().__init__()
            self.connected = connected
            self.model = model

    class SetStreaming(TextualMessage):
        def __init__(self, streaming: bool) -> None:
            super().__init__()
            self.streaming = streaming

    class SetError(TextualMessage):
        def __init__(self, message: str) -> None:
            super().__init__()
            self.message = message

    # ── State ────────────────────────────────────────────────────────────────

    _connected: bool = False
    _model: str = "–"
    _streaming: bool = False
    _error: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="status-indicator", markup=True)
        yield Static("", id="status-model", markup=True)
        yield Static(
            "[#2d4a2d]🌲 No cloud. No tracking. Straight from the Black Forest.[/#2d4a2d]",
            id="status-tagline",
            markup=True,
        )

    # ── Message Handlers ─────────────────────────────────────────────────────

    def on_status_bar_set_status(self, event: "StatusBar.SetStatus") -> None:
        self._connected = event.connected
        self._model = event.model
        self._error = ""
        self.remove_class("error")
        self._update_display()

    def on_status_bar_set_streaming(self, event: "StatusBar.SetStreaming") -> None:
        self._streaming = event.streaming
        if event.streaming:
            self.add_class("streaming")
        else:
            self.remove_class("streaming")
        self._update_display()

    def on_status_bar_set_error(self, event: "StatusBar.SetError") -> None:
        self._error = event.message
        self._streaming = False
        self.remove_class("streaming")
        self.add_class("error")
        self._update_display()

    # ── Rendering ────────────────────────────────────────────────────────────

    def _update_display(self) -> None:
        indicator = self.query_one("#status-indicator", Static)
        model_label = self.query_one("#status-model", Static)

        if self._error:
            indicator.update(f"[bold #ff6b35]⚠  {self._error}[/bold #ff6b35]")
            model_label.update("")
            return

        if self._streaming:
            indicator.update("[#a8c5a0]⏳ Generating…[/#a8c5a0]")
        elif self._connected:
            indicator.update("[#39ff14]●  Ollama: connected[/#39ff14]")
        else:
            indicator.update("[#ff6b35]✗  Ollama: offline[/#ff6b35]")

        model_label.update(f"[#5a7a5a]  │  {self._model}[/#5a7a5a]")
