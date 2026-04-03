# Contributing to MiMi Nox

Danke für dein Interesse! MiMi Nox ist ein privates Projekt von MiMi Tech AI UG –  
externe Contributions sind willkommen, solange sie zum Projekt-Spirit passen:  
**Privat. Lokal. Kein Cloud-Overhead.**

---

## Development Setup

```bash
git clone https://github.com/mimiai/mimi-nox
cd mimi-nox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
playwright install chromium   # für Headless-Browser-Tests
```

---

## Coding Standards

- **Python:** PEP 8, Type Hints überall, `async/await` konsequent
- **JavaScript:** ES2022+, ES-Module (`import/export`), kein Framework, kein Bundler
- **CSS:** Custom Properties (`var(--green)` etc.), kein Tailwind, kein SCSS
- **Tests:** TDD – Tests zuerst schreiben, BDD-Notation (Given-When-Then)
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`)

---

## Tests

```bash
# Alle Tests
pytest tests/ -v

# Einzelnes Modul
pytest tests/test_artifact_detector.py -v

# Ohne Integrationstests (kein Ollama nötig)
pytest tests/ -v -m "not integration"
```

Neue Features **müssen** mit Tests kommen. Keine Tests → kein Merge.

---

## Neue Features hinzufügen

### Neues Tool

1. Funktion in `core/tools.py` implementieren (async, type-annotiert)
2. In `TOOLS`-Liste registrieren
3. Tests in `tests/test_tools.py` schreiben

### Neuer API-Endpunkt

1. Route in `server/routes/<name>.py` anlegen
2. In `server/main.py` registrieren
3. Tests in `tests/test_api.py` erweitern
4. README API-Referenz aktualisieren

### Neuer Skill

Einfach eine Markdown-Datei in `skills/` anlegen – kein Python nötig.

---

## Projekt-Spirit

- ✅ Lokale Ausführung, null Cloud-Dependencies
- ✅ Privacy by design
- ✅ Async everywhere (keine blocking calls im Hauptthread)
- ❌ Keine API-Keys als Pflicht
- ❌ Keine externen Analytics/Telemetry
- ❌ Kein React/Vue/Angular im Frontend

---

*MiMi Tech AI UG – Bad Liebenzell, Schwarzwald 🌲*
