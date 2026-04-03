#!/usr/bin/env python3
"""
◑ MiMi Nox – Server starten
run_server.py

Startet den FastAPI Server auf Port 8765.
Verwendung:
    python run_server.py             # Standard
    python run_server.py --port 9000 # Anderer Port
    python run_server.py --reload    # Dev-Modus mit Auto-Reload
"""
import argparse
import sys
from pathlib import Path

# Sicherstellen dass das MiMi-Nox-Verzeichnis im Pfad ist
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="◑ MiMi Nox API Server")
    parser.add_argument("--host",   default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port",   default=8765, type=int, help="Port (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Auto-Reload im Dev-Modus")
    args = parser.parse_args()

    print(f"\n  ◑ MiMi Nox API Server")
    print(f"  ─────────────────────────────────────")
    print(f"  URL:    http://{args.host}:{args.port}")
    print(f"  Docs:   http://{args.host}:{args.port}/api/docs")
    print(f"  Reload: {'aktiviert' if args.reload else 'deaktiviert'}")
    print(f"  ─────────────────────────────────────\n")

    uvicorn.run(
        "server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
