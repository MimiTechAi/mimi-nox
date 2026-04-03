#!/usr/bin/env bash
# ============================================================
#  ◑ MiMi Nox – Local AI Assistant
#  install.sh – One-command setup
#
#  Usage:
#    git clone https://github.com/mimiai/mimi-nox
#    cd mimi-nox
#    ./install.sh
#
#  MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
#  No cloud. No tracking. 🌲
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
NEON='\033[38;5;82m'
DIM='\033[2m'
BOLD='\033[1m'
RED='\033[0;31m'
NC='\033[0m'

MIMI_NOX_MODEL="${MIMI_NOX_MODEL:-gemma4:e4b}"

banner() {
  echo ""
  echo -e "${NEON}${BOLD}  🌲 ◑ MiMi Nox – Local AI Assistant${NC}"
  echo -e "${DIM}  MiMi Tech AI UG · Bad Liebenzell, Schwarzwald${NC}"
  echo ""
}

step() { echo -e "${GREEN}▶${NC} ${BOLD}$1${NC}"; }
info() { echo -e "  ${DIM}$1${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

banner

# ── 1. Check Python ──────────────────────────────────────────────────────────
step "Python 3.10+ prüfen"
PYTHON=$(command -v python3 || command -v python || fail "Python nicht gefunden. Installiere Python 3.10+")
PY_VERSION=$("$PYTHON" -c "import sys; print(sys.version_info[:2])")
info "Gefunden: $PYTHON ($PY_VERSION)"
"$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
  || fail "Python 3.10+ benötigt. Akt. Version: $PY_VERSION"
ok "Python OK"

# ── 2. Check / Install Ollama ─────────────────────────────────────────────────
step "Ollama prüfen"
if command -v ollama >/dev/null 2>&1; then
  OLLAMA_VER=$(ollama --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "0.0.0")
  ok "Ollama bereits installiert (v${OLLAMA_VER})"

  # Gemma4 E4B benötigt mindestens Ollama v0.20.0
  MIN_VER="0.20.0"
  if printf '%s\n' "$MIN_VER" "$OLLAMA_VER" | sort -V | head -1 | grep -qv "$MIN_VER"; then
    info "Ollama v${OLLAMA_VER} ist zu alt für ${MIMI_NOX_MODEL} (min. v${MIN_VER})."
    info "Aktualisiere Ollama..."
    if [[ "$(uname)" == "Darwin" ]]; then
      brew upgrade ollama 2>/dev/null || curl -fsSL https://ollama.com/install.sh | sh
    else
      curl -fsSL https://ollama.com/install.sh | sh
    fi
    ok "Ollama aktualisiert auf $(ollama --version 2>/dev/null || echo 'neueste Version')"
  fi
else
  info "Ollama nicht gefunden – wird installiert..."
  if [[ "$(uname)" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install ollama
    else
      info "Lade Ollama via curl..."
      curl -fsSL https://ollama.com/install.sh | sh
    fi
  elif [[ "$(uname)" == "Linux" ]]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    fail "Automatische Ollama-Installation nur auf macOS/Linux möglich.\nBitte manuell installieren: https://ollama.com"
  fi
  ok "Ollama installiert"
fi

# ── 3. Ollama starten (falls nicht läuft) ────────────────────────────────────
step "Ollama Service prüfen"
if ! ollama list >/dev/null 2>&1; then
  info "Ollama läuft nicht – starte im Hintergrund..."
  ollama serve &>/dev/null &
  OLLAMA_PID=$!
  sleep 3
  if ! ollama list >/dev/null 2>&1; then
    fail "Ollama konnte nicht gestartet werden. Führe 'ollama serve' manuell aus."
  fi
  info "Ollama PID: $OLLAMA_PID"
fi
ok "Ollama läuft"

# ── 4. Modell pullen ──────────────────────────────────────────────────────────
step "Modell: ${MIMI_NOX_MODEL}"
if ollama show "${MIMI_NOX_MODEL}" >/dev/null 2>&1; then
  ok "${MIMI_NOX_MODEL} bereits vorhanden"
else
  info "Lade ${MIMI_NOX_MODEL} herunter..."
  info "(einmalig ~2.5 GB – dauert je nach Internet 2-5 Min)"
  echo ""
  ollama pull "${MIMI_NOX_MODEL}"
  echo ""
  ok "${MIMI_NOX_MODEL} bereit"
fi

# ── 5. Python venv + Dependencies ────────────────────────────────────────────
step "Python-Umgebung einrichten"
if [[ ! -d ".venv" ]]; then
  info "Erstelle Virtual Environment..."
  "$PYTHON" -m venv .venv
fi
info "Installiere Dependencies (inkl. chromadb – kann 1-2 Min dauern)..."
.venv/bin/pip install -q -e "." 2>&1 | tail -3
ok "Dependencies installiert (ddgs, chromadb, textual, ollama)"

# ── 5b. nomic-embed-text für Memory ──────────────────────────────────────────
step "Embedding-Modell für Memory"
if ollama show "nomic-embed-text" >/dev/null 2>&1; then
  ok "nomic-embed-text bereits vorhanden"
else
  info "Lade nomic-embed-text (~274 MB) für persistentes Memory..."
  ollama pull nomic-embed-text
  ok "nomic-embed-text bereit"
fi

# ── 6. Fertig ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${NEON}${BOLD}  ✅ Setup abgeschlossen!${NC}"
echo ""
echo -e "  ${BOLD}Starten mit:${NC}"
echo -e "  ${NEON}.venv/bin/python run_server.py${NC}"
echo -e "  → öffne ${NEON}http://127.0.0.1:8765${NC} im Browser"
echo ""
echo -e "  ${DIM}TUI-Modus (alternativ):${NC}"
echo -e "  ${DIM}.venv/bin/mimi-nox${NC}"
echo ""
echo -e "  ${DIM}Anderes Modell beim Setup:${NC}"
echo -e "  ${DIM}MIMI_NOX_MODEL=llama3.1 ./install.sh${NC}"
echo ""
echo -e "${DIM}  🌲 No cloud. No tracking. Straight from the Black Forest.${NC}"
echo ""

# Optional: direkt starten?
if [[ -t 0 ]]; then
  read -rp "  Jetzt starten? [J/n] " REPLY
  REPLY="${REPLY:-J}"
  if [[ "$REPLY" =~ ^[JjYy]$ ]]; then
    echo -e "\n  ${NEON}▶${NC} Öffne ${NEON}http://127.0.0.1:8765${NC} im Browser\n"
    exec .venv/bin/python run_server.py
  fi
fi
