"""
ClawDash – BlackForest Edition
MiMi Tech AI UG – Bad Liebenzell, Schwarzwald

Entry Point: clawdash [--model MODEL] [--reset]
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clawdash",
        description=(
            "🌲 ClawDash – BlackForest Edition\n"
            "   Keyboard-first TUI for local LLMs via Ollama.\n"
            "   MiMi Tech AI UG · Bad Liebenzell, Schwarzwald\n\n"
            "Slash commands:  /post  /debug  /idea  /explain  /commit\n"
            "Swarm agents:    /swarm <Aufgabe>  (multi-agent parallel pipeline)\n"
            "Keyboard:        Ctrl+R=Reset  Ctrl+L=Clear  ↑↓=History  q=Quit"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  clawdash\n"
            "  clawdash --model llama3.1\n"
            "  clawdash --model qwen2.5-coder:7b\n"
            "  clawdash --reset\n\n"
            "No cloud. No tracking. Straight from the Black Forest. 🌲"
        ),
    )
    parser.add_argument(
        "--model",
        default="phi4-mini",
        metavar="MODEL",
        help="Ollama model name (default: phi4-mini). "
             "Run 'ollama list' to see available models.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear previous session on start",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ClawDash 3.0.0 – BlackForest Edition (MiMi Tech AI UG)",
    )

    args = parser.parse_args()

    try:
        from ui.app import ClawDashApp
    except ImportError as e:
        print(f"[Error] Failed to import ClawDash: {e}", file=sys.stderr)
        print("Run: pip install -e '.[dev]'  or  ./install.sh", file=sys.stderr)
        sys.exit(1)

    app = ClawDashApp(model=args.model, reset=args.reset)
    app.run()


if __name__ == "__main__":
    main()
