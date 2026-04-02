"""
ClawDash Slash Commands – BlackForest Edition

Extensible command registry. Add your own commands in 30 seconds:

    COMMANDS["/mycmd"] = "Do something awesome with: {input}"

Commands are resolved before sending to Ollama.
The {input} placeholder is replaced with the user's text after the command.

Example:
    User types:  /post AI productivity
    Resolves to: "Write a professional LinkedIn post about... AI productivity"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Format: "/command": "Prompt template with optional {input} placeholder"

COMMANDS: dict[str, str] = {
    "/post": (
        "Write a professional, authentic LinkedIn post about the following topic. "
        "Keep it concise (max 150 words), engaging, and avoid corporate buzzwords. "
        "Topic: {input}"
    ),
    "/debug": (
        "You are a senior software engineer with 15 years of experience. "
        "Carefully analyze the following code for bugs, edge cases, performance issues, "
        "and improvements. Be specific and explain your reasoning. "
        "Code:\n{input}"
    ),
    "/idea": (
        "Generate exactly 5 creative, actionable startup ideas related to: {input}\n\n"
        "For each idea use this format:\n"
        "**Name** | Problem | Solution | Why now\n\n"
        "Be concrete, not generic."
    ),
    "/explain": (
        "Explain the following concept clearly and simply, "
        "as if explaining to a smart developer who has never encountered it before. "
        "Use analogies if helpful. Concept: {input}"
    ),
    "/commit": (
        "Write a conventional Git commit message for the following changes. "
        "Use the format: <type>(<scope>): <short description>\n\n"
        "Then add a brief body if needed. Changes:\n{input}"
    ),
    # /swarm is handled specially by the App (triggers multi-agent pipeline)
    # The template here is only used as a fallback usage hint.
    "/swarm": "__swarm__:{input}",
}

# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

_COMMAND_DESCRIPTIONS: dict[str, str] = {
    "/post":    "Write a LinkedIn post",
    "/debug":   "Debug code as a senior engineer",
    "/idea":    "Generate 5 startup ideas",
    "/explain": "Explain a concept simply",
    "/commit":  "Write a Git commit message",
    "/swarm":   "Multi-agent parallel pipeline",
}

# Commands that trigger special app-level behaviour (not resolved to a prompt)
SWARM_COMMANDS: frozenset[str] = frozenset({"/swarm"})


def resolve_command(raw_input: str) -> str:
    """
    Resolve a slash command to its full prompt.

    Examples:
        resolve_command("/post AI trends")
        → "Write a professional LinkedIn post about... AI trends"

        resolve_command("/post")
        → "[/post] Usage: /post <topic>  —  Write a LinkedIn post"

        resolve_command("/unknown foo")
        → "/unknown foo"   (passthrough, no match)

        resolve_command("hello")
        → "hello"          (passthrough, no slash)

    Returns:
        The resolved prompt string, or the original input if no match.
    """
    raw_input = raw_input.strip()

    if not raw_input.startswith("/"):
        return raw_input

    parts = raw_input.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command not in COMMANDS:
        return raw_input  # unknown command → passthrough

    template = COMMANDS[command]

    if "{input}" in template:
        if not argument:
            desc = _COMMAND_DESCRIPTIONS.get(command, "")
            return (
                f"[{command}] Usage: {command} <text>  "
                f"{'— ' + desc if desc else ''}"
            )
        return template.replace("{input}", argument)

    # Template has no {input} placeholder → append argument if present
    return template + (" " + argument if argument else "")


def get_completions(prefix: str) -> list[str]:
    """
    Return all commands that start with the given prefix.
    Used for Tab-completion in HistoryInput.

    Example:
        get_completions("/po") → ["/post"]
        get_completions("/")   → ["/post", "/debug", "/idea", "/explain", "/commit"]
    """
    return [cmd for cmd in COMMANDS if cmd.startswith(prefix)]


def get_command_help() -> list[tuple[str, str]]:
    """Return list of (command, description) for the help overlay."""
    return [
        (cmd, _COMMAND_DESCRIPTIONS.get(cmd, ""))
        for cmd in COMMANDS
    ]


def is_command(text: str) -> bool:
    """Return True if text starts with a known slash command."""
    parts = text.strip().split(maxsplit=1)
    return bool(parts) and parts[0].lower() in COMMANDS


def is_swarm_command(text: str) -> bool:
    """Return True if text is a /swarm command (handled by swarm pipeline)."""
    parts = text.strip().split(maxsplit=1)
    return bool(parts) and parts[0].lower() in SWARM_COMMANDS


def extract_swarm_task(text: str) -> str:
    """
    Extract the task from a /swarm command.
    "/swarm Plan a REST API" → "Plan a REST API"
    "/swarm" → ""  (caller should show usage hint)
    """
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
