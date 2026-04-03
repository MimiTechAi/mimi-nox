# ◑ MiMi Nox

<div align="center">

**Dein privater, lokaler KI-Agent. Ohne Cloud. Ohne Tracking. Aus dem Schwarzwald.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Powered%20by-Ollama-black?style=flat-square)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-25%20modules-22c55e?style=flat-square)](#testing)

*Built in Bad Liebenzell, Schwarzwald · No cloud · No telemetry · 100% yours*

</div>

---

## Was ist MiMi Nox?

MiMi Nox ist ein **vollständig lokaler, autonomer AI-Agent** – kein Abonnement, keine API-Keys, kein Cloud-Zwang. Er läuft als Web-App mit Premium-Browser-Interface (inkl. PWA / Handy-Support) und nutzt **Gemma 4** über Ollama direkt auf deiner Maschine.

> "Dein Rechner schläft nie. MiMi auch nicht."

---

## Features auf einen Blick

### 🤖 KI-Kern
| Feature | Details |
|---|---|
| **ReAct + Reflexion** | Selbstkorrigierende Antworten mit eingebautem Qualitäts-Check |
| **Tool Calling** | Web-Suche, Shell, Dateisuche, Vision, Browser-Steuerung |
| **Swarm Pipeline** | Multi-Agent-Parallel-Ausführung via `/swarm` |
| **Streaming** | Token-by-Token-Ausgabe, kein Warten |
| **Thinking Mode** | Echtzeit-Reasoning-Visualisierung (Gemma 4 native) |

### 🗂 Gedächtnis & Kontext
| Feature | Details |
|---|---|
| **Vektorspeicher** | Semantisches Langzeitgedächtnis (ChromaDB) |
| **Session-Persistence** | Nahtlose Fortsetzung via atomic-write JSON |
| **User-Profil** | Lernende Persona – Name, Expertise, Sprache, Stil |
| **Fehler-Journal** | Sammelt Korrekturen, verhindert Wiederholung |

### 🛠 Autonome Werkzeuge
| Tool | Was es tut |
|---|---|
| `web_search` | DuckDuckGo-Suche + Context-Extraktion |
| `browser_go` | **Headless Playwright** – echter Browser mit Cookie-Handling |
| `shell_exec` | Shell-Befehle mit Sandbox-Bestätigung |
| `file_search` | Ripgrep-basierte Dateisuche |
| `vision_click` | Bildschirm-Screenshot → KI-Koordinaten → Maus-Klick (PyAutoGUI) |
| `vision_type` | Text tippen über GUI-Steuerung |
| `datetime_now` | Aktuelle Uhrzeit und Datum |

### 🌐 Browser Interface (Hauptinterface)
| Feature | Details |
|---|---|
| **Streams live** | SSE-basiert, Token erscheinen sofort |
| **Artifacts Panel** | Code/HTML in Seitenleiste statt im Chat-Verlauf |
| **Markdown Rendering** | marked.js + DOMPurify, inkl. Syntax-Highlighting |
| **Memory Tab** | Vektorspeicher direkt im Browser durchsuchen |
| **Skills Tab** | Eigene Skills erstellen, bearbeiten, löschen |
| **Voice / Walkie-Talkie** | Whisper-Transkription + nativer TTS |
| **PWA** | Installierbar als App, funktioniert offline |
| **Mobile Zen-Modus** | Schlankes Mobile-UI via QR-Code-Pairing |
| **Hintergrund-Jobs** | APScheduler – zeitgesteuerte Tasks via `/api/schedule` |

### 📱 PWA & Mobile
- QR-Code-Pairing im Browser (`◑ Mobil verbinden`)
- Desktop zeigt Verbindungsbestätigung
- Mobile-UI: nur Chat, kein Overhead
- Installierbar auf iOS (Safari → Zum Home-Bildschirm) und Android

---

## Schnellstart

**Voraussetzungen:** Python 3.10+, [Ollama](https://ollama.com) installiert und laufend.

### Ein-Befehl-Setup

```bash
git clone https://github.com/mimiai/mimi-nox
cd mimi-nox
./install.sh
```

Das Skript erledigt alles:
1. Python-Version prüfen (≥ 3.10)
2. Ollama installieren (falls fehlt)
3. `gemma4:e4b` herunterladen (~2.5 GB, einmalig)
4. Virtuelle Umgebung + alle Abhängigkeiten installieren
5. Optionaler Sofortstart

### Manuell / Entwicklung

```bash
git clone https://github.com/mimiai/mimi-nox
cd mimi-nox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
```

---

## Starten

```bash
# Web-App (empfohlen)
python run_server.py

# Mit Optionen
python run_server.py --port 9000
python run_server.py --reload      # Dev-Modus: Auto-Reload bei Änderungen

# TUI (Terminal-Alternative)
mimi-nox
mimi-nox --model llama3.3
mimi-nox --reset
```

Dann im Browser: **http://127.0.0.1:8765**

---

## Keyboard Shortcuts

| Taste | Aktion |
|---|---|
| `Enter` | Nachricht senden |
| `Shift+Enter` | Neue Zeile |
| `↑` / `↓` | Eingabe-Verlauf navigieren |
| `Esc` | Eingabe leeren · Panel schließen |
| `Tab` | Slider / Panel resizen (Artifact Panel) |

---

## Slash Commands

Starte mit `/` für den Command-Modus.

| Befehl | Funktion |
|---|---|
| `/learn <Thema>` | MiMi lernt dein Workflow-Wissen als neuen Skill |
| `/post <Thema>` | LinkedIn-Post schreiben |
| `/debug <Code>` | Code debuggen wie ein Senior Engineer |
| `/idea <Thema>` | 5 Startup-Ideen generieren |
| `/explain <Konzept>` | Einfach erklären |
| `/commit <Änderungen>` | Conventional Commit Message |
| `/swarm <Aufgabe>` | Multi-Agent-Pipeline starten |
| `/schedule <Cron> "<Task>"` | Hintergrund-Job einrichten |

### Eigenen Befehl in 30 Sekunden

```python
# core/commands.py
COMMANDS["/mycmd"] = "Mach etwas Geniales mit: {input}"
```

Neustart → fertig.

---

## Artifacts Panel

Inspiriert von Claude's Artifact-System: Wenn MiMi Code oder HTML generiert, erscheint dieser **nicht im Chat**, sondern öffnet sich in einem schlanken Seitenpanel.

```
┌─────────────────────────┐  ┌──────────────────────────────┐
│ Chat                    │  │ 📄 script.py   [Python]      │
│                         │  │──────────────────────────────│
│ Hier ist dein Skript:   │  │ import os                    │
│                         │  │ from pathlib import Path     │
│ [📄 script.py → Öffnen] │  │                              │
│                         │  │ def find_files(path):        │
└─────────────────────────┘  └──────────────────────────────┘
```

**Features des Panels:**
- Syntax-Highlighting (highlight.js, 14 Sprachen)
- HTML-Preview in sandboxed `<iframe>`
- Copy / Download-Button
- Session-Verlauf als Navigations-Dots (●●●)
- Drag-to-Resize (320–800px)
- `Esc` schließt das Panel

**Triggerlogik:** Code-Blöcke mit ≥ 5 Zeilen werden automatisch als Artifact erkannt.

---

## Skills System

Skills sind Markdown-Dateien die MiMi mit Spezialwissen ausstatten.

```
skills/
├── code-reviewer.md      Code Review als Senior Engineer
├── file-assistant.md     Datei-Management-Assistent
├── shell-helper.md       Terminal-Experte
├── vision-assistant.md   GUI-Automatisierung & Screen-Steuerung
├── web-researcher.md     Headless Web-Recherche-Agent
└── writer.md             Content-Writing-Assistent
```

### Eigenen Skill erstellen

**Option 1: Via Chat**
```
/learn Wie wir unsere FastAPI-Routen strukturieren
```
MiMi analysiert dein Projekt, erstellt den Skill automatisch und fügt ihn sofort ein.

**Option 2: Manuell** – Datei in `skills/` anlegen:

```markdown
---
name: mein-skill
trigger: /mein-trigger
description: Was dieser Skill macht
tools:
  - shell_exec
  - web_search
---

## Dein System-Prompt hier

Anleitung was MiMi in diesem Modus tun soll...
```

**Option 3: Skills Tab im Browser** – GUI-Editor direkt in der App.

---

## Hintergrund-Jobs (Scheduler)

MiMi kann Tasks zeitgesteuert im Hintergrund erledigen:

```bash
# Via Chat
/schedule "täglich 08:00" "Erstelle einen Tages-Briefing zu Tesla-News"

# Via API
POST /api/schedule
{
  "cron": "0 8 * * *",
  "task": "Erstelle einen Tages-Briefing zu Tesla-News",
  "job_id": "morning-briefing"
}
```

Ergebnisse abrufbar via:
```
GET /api/schedule/results
GET /api/schedule/{job_id}
DELETE /api/schedule/{job_id}
```

---

## Visual Computer Use

MiMi kann deinen Desktop wie ein Mensch bedienen:

```
1. Screenshot des Bildschirms machen
2. Vision-Modell analysiert: "Wo ist der 'Speichern'-Button?"
3. X/Y-Koordinaten berechnen
4. Maus-Klick ausführen
```

> **Hinweis (macOS):** Systemeinstellungen → Datenschutz → Bedienungshilfen **und** Bildschirmaufnahme für das Terminal aktivieren.

---

## Headless Browser

Für echte Web-Recherche ohne Scraping-Grenzen:

```python
# Playwright-Browser öffnet sich unsichtbar
# Cookie-Banner werden via Vision erkannt und akzeptiert
# Text wird extrahiert (max. 15.000 Zeichen, OOM-sicher)
```

---

## API-Referenz

Der Server läuft auf `http://127.0.0.1:8765`. Swagger-Docs: `/api/docs`

### Chat

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `POST` | `/api/chat` | Synchroner Chat (wartet auf vollständige Antwort) |
| `POST` | `/api/chat/stream` | SSE-Stream (empfohlen) |
| `POST` | `/api/chat/approve` | Sandbox-Tool-Bestätigung |

**Stream-Request:**
```json
{
  "message": "Schreib mir ein Python-Skript",
  "model": "gemma4:e4b",
  "history": [],
  "autonomous": false
}
```

**SSE-Event-Typen:**

| Type | Payload | Bedeutung |
|---|---|---|
| `thinking_start` | – | Reasoning beginnt |
| `thinking` | `data: "..."` | Reasoning-Token |
| `chunk` | `data: "..."` | Antwort-Token |
| `activity` | `cmd, status` | Tool-Aufruf (Terminal-Anzeige) |
| `replace_text` | `text: "..."` | Chat-Bubble durch bereinigten Text ersetzen |
| `artifact` | `artifact: {...}` | Code-Artifact → Panel öffnen |
| `reflect` | `status, needs_revision` | Qualitätsprüfung |
| `revision` | `reason: "..."` | Überarbeitung eingeleitet |
| `skill_created` | `skill: {...}` | Neuer Skill angelegt |
| `error` | `msg: "..."` | Fehler |
| `done` | – | Stream beendet |

### Memory

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `GET` | `/api/memory` | Alle Einträge |
| `GET` | `/api/memory/search?q=...` | Semantische Suche |
| `DELETE` | `/api/memory/{id}` | Eintrag löschen |

### Skills

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `GET` | `/api/skills` | Alle Skills |
| `POST` | `/api/skills` | Skill erstellen |
| `PUT` | `/api/skills/{name}` | Skill aktualisieren |
| `DELETE` | `/api/skills/{name}` | Skill löschen |

### Weitere Endpunkte

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `GET` | `/api/health` | Server-Status + Ollama-Verbindung |
| `GET` | `/api/profile` | User-Profil laden |
| `POST` | `/api/profile` | User-Profil speichern |
| `POST` | `/api/audio/transcribe` | Whisper-Transkription |
| `POST` | `/api/audio/tts` | Text-to-Speech |
| `GET` | `/api/mobile/status` | Mobile-Verbindungsstatus |
| `POST` | `/api/mobile/ping` | Mobile-Verbindung registrieren |

---

## Architektur

```
mimi-nox/
│
├── run_server.py              Web-App-Einstiegspunkt
├── clawdash.py                TUI-Einstiegspunkt + CLI
├── install.sh                 One-Command-Setup-Skript
├── pyproject.toml             Package-Konfiguration
│
├── core/                      Reines Async-Python – kein UI
│   ├── chat.py                Ollama AsyncClient + Streaming
│   ├── react.py               ReAct-Loop + Reflexion
│   ├── tools.py               Tool-Engine (7 Tools)
│   ├── artifact_detector.py   Code-Block-Erkennung für Artifacts
│   ├── browser.py             Playwright Headless Browser
│   ├── vision.py              PyAutoGUI + Screenshot-Analyse
│   ├── vision_memory.py       Koordinaten-Lerngedächtnis
│   ├── scheduler.py           APScheduler Hintergrund-Jobs
│   ├── skill_builder.py       Auto-Skill-Generierung via /learn
│   ├── skills.py              Skill-Loader + CRUD
│   ├── commands.py            Slash-Command-Registry
│   ├── swarm.py               Multi-Agent-Parallel-Pipeline
│   ├── memory.py              ChromaDB Vektorspeicher
│   ├── session.py             JSON-Persistence (atomic write)
│   ├── profile.py             User-Profil (JSON)
│   ├── corrections.py         Fehler-Journal
│   ├── feedback.py            👍/👎 Feedback-Store
│   ├── transcribe.py          Faster-Whisper STT
│   └── types.py               Message TypedDict
│
├── server/                    FastAPI Backend
│   ├── main.py                App-Factory + CORS + Static Files
│   └── routes/
│       ├── chat.py            POST /chat + SSE /chat/stream
│       ├── memory.py          GET/DELETE /memory
│       ├── skills.py          CRUD /skills
│       ├── profile.py         GET/POST /profile
│       ├── audio.py           POST /audio/transcribe + /tts
│       ├── mobile.py          GET/POST /mobile
│       ├── schedule.py        CRUD /schedule
│       ├── feedback.py        POST /feedback
│       └── health.py          GET /health
│
├── app/src/                   Web-Frontend (kein Framework)
│   ├── index.html             App-Shell + PWA-Meta
│   ├── main.js                NoxApp Controller (ES-Modul)
│   ├── artifact.js            ArtifactStore + ArtifactPanel
│   ├── style.css              Schwarzwald-Edition Design-System
│   ├── manifest.json          PWA-Manifest
│   └── service-worker.js      Cache-First SW (v5)
│
├── skills/                    Eingebaute Skill-Definitionen
├── ui/                        TUI (Textual) – Alternative
└── tests/                     25 Test-Module (pytest)
```

---

## Entwicklung

```bash
# Dev-Setup
pip install -e ".[dev,voice]"

# Tests ausführen
pytest tests/ -v

# Nur schnelle Unit-Tests
pytest tests/ -v -m "not slow"

# Einzelnes Modul
pytest tests/test_artifact_detector.py -v

# Web-App mit Auto-Reload
python run_server.py --reload

# Playwright-Browser installieren (einmalig)
playwright install chromium
```

---

## Testing

**25 Test-Module** mit pytest. Strategie: TDD mit BDD-Notation (Given-When-Then).

| Modul | Testet |
|---|---|
| `test_artifact_detector.py` | Artifact-Erkennung (11 Tests, BDD) |
| `test_api.py` | Alle REST-Endpunkte |
| `test_chat.py` | Ollama-Streaming + Fehlerbehandlung |
| `test_tools.py` | Tool-Engine, alle 7 Tools |
| `test_react.py` | ReAct-Loop + Reflexionslogik |
| `test_skills.py` | Skill-Loader, CRUD, Trigger |
| `test_skill_builder.py` | Auto-Skill-Generierung |
| `test_memory.py` | ChromaDB-Vektorspeicher |
| `test_vision.py` | Screenshot + Koordinaten-Erkennung |
| `test_swarm.py` | Multi-Agent-Parallel-Pipeline |
| `test_audio.py` | Whisper-Transkription + TTS |
| ... | + 14 weitere |

---

## Systemanforderungen

| | Minimum | Empfohlen |
|---|---|---|
| **OS** | macOS 13+ / Ubuntu 22+ | macOS 14+ |
| **Python** | 3.10 | 3.12+ |
| **RAM** | 8 GB | 16 GB+ |
| **Storage** | 5 GB (Modell + Deps) | 20 GB+ |
| **GPU** | – | M1/M2/M3 oder NVIDIA |

---

## Sicherheit & Datenschutz

- **Keine Daten verlassen deinen Rechner** – kein Cloud-Endpunkt, kein Tracking
- **Shell-Sandbox**: Tool-Aufrufe benötigen Bestätigung (außer im `autonomous`-Modus)
- **Iframe-Sandbox**: HTML-Artifacts laufen in `sandbox="allow-scripts"` ohne Netzwerkzugriff
- **DOMPurify**: Alle Markdown-Ausgaben werden XSS-bereinigt
- **macOS-Permissions**: Vision-Tools benötigen Bedienungshilfen + Bildschirmaufnahme

---

## Lizenz

MIT — [MiMi Tech AI UG](https://mimiai.de), Bad Liebenzell, Schwarzwald  
© 2026 MiMi Tech AI UG. Alle Rechte vorbehalten.

---

<div align="center">

*No cloud. No tracking. Straight from the Black Forest. 🌲*

</div>
