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
        description="🌲 ClawDash – BlackForest Edition | keyboard-first TUI for local LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  clawdash\n"
            "  clawdash --model mistral\n"
            "  clawdash --reset\n\n"
            "Keyboard:\n"
            "  Enter     send message\n"
            "  ↑ / ↓    input history\n"
            "  /         command mode (try /post, /debug, /idea)\n"
            "  Ctrl+R    reset session\n"
            "  Ctrl+L    clear display\n"
            "  q         quit\n\n"
            "No cloud. No tracking. Straight from the Black Forest.\n"
            "MiMi Tech AI UG – Bad Liebenzell"
        ),
    )
    parser.add_argument(
        "--model",
        default="llama3.2",
        metavar="MODEL",
        help="Ollama model name (default: llama3.2)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear previous session on start",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ClawDash 3.0.0 – BlackForest Edition",
    )

    args = parser.parse_args()

    try:
        from ui.app import ClawDashApp
    except ImportError as e:
        print(f"[Error] Failed to import ClawDash: {e}", file=sys.stderr)
        print("Run: pip install textual ollama", file=sys.stderr)
        sys.exit(1)

    app = ClawDashApp(model=args.model, reset=args.reset)
    app.run()


if __name__ == "__main__":
    main()
