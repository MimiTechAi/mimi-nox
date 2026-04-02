# Changelog

All notable changes to ClawDash – BlackForest Edition are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [3.0.0] – 2026-04-02

### Added
- Initial release – ClawDash v3 BlackForest Edition
- Async streaming via Ollama AsyncClient (`@work(exclusive=True)` Textual worker)
- HistoryInput widget with ↑/↓ navigation and Tab command completion
- ChatView with RichLog streaming (chunk-by-chunk, no blocking)
- StatusBar with live Ollama connection status and BlackForest tagline
- Session persistence with atomic writes (`tmpfile + rename()`)
- Slash commands: `/post`, `/debug`, `/idea`, `/explain`, `/commit`
- Extensible command registry (`COMMANDS` dict in `core/commands.py`)
- Full error handling: Ollama offline, model not found, stream abort, corrupt session
- Input disabled during streaming (prevents race conditions)
- `--model` and `--reset` CLI flags
- BlackForest Edition color palette (Schwarzwald Neon: `#39ff14` on `#080b08`)
- External TCSS theming file (`ui/clawdash.tcss`)
- `Message` TypedDict as shared contract between all modules
- `pytest-asyncio` test suite with `asyncio_mode = auto`

### Architecture
- Modular structure: `core/` (chat, commands, session, types) + `ui/` (app, widgets, tcss)
- No Textual dependencies in core modules (pure async Python)
- Workers communicate with UI exclusively via `post_message()` (thread-safe)

---

*MiMi Tech AI UG – Bad Liebenzell, Schwarzwald*  
*No cloud. No tracking. Straight from the Black Forest. 🌲*
