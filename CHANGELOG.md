# Changelog

Alle wesentlichen Änderungen an **MiMi Nox** werden hier dokumentiert.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Planned
- Multi-Session-Verwaltung (parallele Chats)
- Plugin-API für externe Skill-Pakete
- Lokales Embedding-Modell (statt ChromaDB default)

---

## [4.0.0] – 2026-04-03

### Added – Artifacts Panel
- `core/artifact_detector.py`: Regex-Engine erkennt Code-Blöcke (≥ 5 Zeilen) in LLM-Output automatisch
- 14 Sprachen unterstützt: Python, Bash, JS/TS, Rust, Go, SQL, HTML, SVG, JSON, YAML, Diff, Markdown
- `app/src/artifact.js`: `ArtifactStore` (Versionierung) + `ArtifactPanel` (Sliding Side Panel)
- Panel-Features: Syntax-Highlighting (highlight.js), HTML-Preview (sandboxed iframe), Copy/Download, Drag-to-Resize (320–800px), Session-Verlauf als Navigations-Dots
- SSE-Events: `artifact` und `replace_text` in der Chat-Stream-Pipeline
- `main.js` auf ES-Module (`type="module"`) umgestellt
- TDD-Suite: 11 BDD-Tests (Given-When-Then) in `tests/test_artifact_detector.py`

### Added – Visual Computer Use
- `core/vision.py`: `vision_click` und `vision_type` (PyAutoGUI + Llama-Vision)
- Screenshot → Koordinaten-Berechnung → Maus-Klick-Ausführung
- HITL (Human-in-the-Loop) Lernmodus: bei Unsicherheit nach manuellem Klick fragen
- `core/vision_memory.py`: Koordinaten-Lerngedächtnis per Element-Label

### Added – Headless Browser
- `core/browser.py`: Playwright-Integration (Chromium, headless)
- Cookie-Banner-Erkennung via Vision + automatische Akzeptierung
- 15.000-Zeichen-Truncation gegen OOM/Context-Flooding
- `PlaywrightBrowserManager`: Singleton mit Concurrency-Safety

### Added – Hintergrund-Scheduler
- `core/scheduler.py`: APScheduler-Integration (cron-basiert, persistent)
- `server/routes/schedule.py`: REST-API (`/api/schedule`)
- Job-Ergebnisse persistent in `scheduled_jobs.json`
- Bugfix: Route-Reihenfolge `/results` vor `/{job_id}` (verhindert Konflikte)

### Added – PWA & Mobile
- `manifest.json`: Dark-Theme (`#020504`), Shortcuts, Display-Overrides
- `service-worker.js` v5: Cache-First für Statics, Network-Only für API/Audio
- Auto-Update-Mechanismus: "🔄 Jetzt aktualisieren"-Toast bei neuem SW
- Mobile Zen-Modus: CSS `mobile-pwa-mode` blendet Desktop-UI auf `≤768px` aus
- QR-Code-Pairing mit Desktop-Bestätigungs-Toast
- PWA-Icons: echte PNG-Icons (192×512px)

### Added – Voice UX
- `core/transcribe.py`: Faster-Whisper STT (lokal)
- `/api/audio/transcribe`: WAV-Upload → Transkript
- `/api/audio/tts`: Native macOS-TTS (kein Cloud)
- Walkie-Talkie-Modus: Automatisches Vorlesen nach Voice-Input
- Waveform-Visualisierung während Aufnahme

### Added – Skills CRUD
- `server/routes/skills.py`: GET/POST/PUT/DELETE `/api/skills`
- Skills-Tab im Browser: GUI-Editor für eigene Skills
- `core/skill_builder.py`: Auto-Skill-Generierung via `/learn <Thema>`
- Skill-Chips im Chat-Bereich (klickbar → Trigger in Input)

### Fixed
- `main.js` `_queryElements()`: fehlende `chatArea`- und `bottombar`-Referenzen → Crash aller Event-Handler auf Desktop behoben
- Null-Guards für alle optionalen DOM-Elemente in `_bindEvents()`
- Service Worker Cache-Invalidierung: automatischer Versionsbump erzwingt saubere Aktualisierung

---

## [3.1.0] – 2026-04-02

### Added
- Web-Interface als primäres Frontend (FastAPI + HTML/JS/CSS)
- SSE-Streaming-Endpunkt (`POST /api/chat/stream`)
- ReAct-Loop mit Reflexion (automatische Qualitätsprüfung + Revision)
- ChromaDB Vektorspeicher (semantisches Langzeitgedächtnis)
- User-Profil (Name, Expertise, Sprache, Kommunikationsstil)
- Fehler-Journal (`core/corrections.py`)
- 👍/👎 Feedback-Store (`core/feedback.py`)
- Thinking-Mode-Visualisierung (Gemma 4 native reasoning)
- Swarm-Pipeline: `/swarm` Multi-Agent-Ausführung
- Mobile-Pairing-Modal mit QR-Code

### Architecture
- Single-Codebase: `core/` vollständig UI-unabhängig
- FastAPI-Server als dünner SSE-Layer über `core/`
- Frontend kommuniziert ausschließlich via REST/SSE

---

## [3.0.0] – 2026-04-01

### Added – ClawDash v3 BlackForest Edition (Initial Release)
- Async-Streaming via Ollama AsyncClient
- TUI-Frontend (Textual): `HistoryInput`, `ChatView`, `StatusBar`
- Slash-Commands: `/post`, `/debug`, `/idea`, `/explain`, `/commit`
- Erweiterbare Command-Registry (`COMMANDS` Dict in `core/commands.py`)
- Session-Persistence mit atomic writes (`tmpfile + rename()`)
- `--model` und `--reset` CLI-Flags
- Schwarzwald-Edition-Farbpalette (`#39ff14` auf `#080b08`)
- `Message` TypedDict als Shared-Contract zwischen allen Modulen
- `pytest-asyncio`-Test-Suite (`asyncio_mode = auto`)

### Architecture
- Modulare Struktur: `core/` (rein async, kein UI) + `ui/` (Textual)
- Workers kommunizieren via `post_message()` (thread-safe)

---

*MiMi Tech AI UG – Bad Liebenzell, Schwarzwald*  
*No cloud. No tracking. Straight from the Black Forest. 🌲*
