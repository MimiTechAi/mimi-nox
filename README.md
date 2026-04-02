# 🌲 ClawDash – BlackForest Edition

> **The most beautiful way to talk to your local LLM.**  
> Built in Bad Liebenzell, Schwarzwald.  
> No cloud. No tracking. Just you, your model, and the forest.

<!-- Demo GIF coming soon -->

---

## Features

| | |
|---|---|
| ⚡ **Streaming** | Responses appear token by token, no waiting |
| ⌨️  **Keyboard-first** | Never touch the mouse |
| 🔒 **100% local** | ollama only – zero cloud, zero telemetry |
| 🗂️  **Session persistence** | Pick up exactly where you left off |
| 🛠️  **Slash commands** | `/post`, `/debug`, `/idea`, `/explain`, `/commit` |
| ➕ **Extensible** | Add your own commands in 30 seconds |

---

## Install

**Requirements:** Python 3.10+, [Ollama](https://ollama.com) running locally.

```bash
pipx install git+https://github.com/mimiai/clawdash
```

Or, for development:

```bash
git clone https://github.com/mimiai/clawdash
cd clawdash
pip install -e ".[dev]"
```

---

## Usage

```bash
clawdash                    # start with default model (llama3.2)
clawdash --model mistral    # use a specific model
clawdash --reset            # clear previous session and start fresh
clawdash --version          # show version
clawdash --help             # show all options
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `↑` / `↓` | Navigate input history |
| `/` | Enter command mode |
| `Tab` | Autocomplete slash command |
| `Ctrl+R` | Reset session (deletes history) |
| `Ctrl+L` | Clear display (keeps session) |
| `q` | Quit |

---

## Slash Commands

Type `/` to enter command mode. `Tab` autocompletes.

| Command | What it does |
|---------|-------------|
| `/post <topic>` | Write a LinkedIn post |
| `/debug <code>` | Debug as a senior engineer |
| `/idea <topic>` | Generate 5 startup ideas |
| `/explain <concept>` | Explain simply |
| `/commit <changes>` | Write a conventional commit message |

### Add your own commands in 30 seconds

Edit `core/commands.py`:

```python
COMMANDS["/mycmd"] = "Do something awesome with: {input}"
```

Restart ClawDash. Done.

---

## Session Persistence

ClawDash automatically saves your session after every message to:

```
~/.clawdash/sessions/default.json
```

On restart:
```
🌲 ClawDash BlackForest Edition — Welcome back.
   Last session restored (12 messages, 2 hours ago).
```

Reset with `Ctrl+R` or `clawdash --reset`.

---

## Architecture

```
clawdash/
├── clawdash.py        Entry point + CLI
├── core/
│   ├── types.py       Message TypedDict
│   ├── chat.py        Ollama async streaming engine
│   ├── commands.py    Slash command registry
│   └── session.py     JSON persistence (atomic writes)
└── ui/
    ├── app.py         Textual app + worker orchestration
    ├── widgets.py     HistoryInput, ChatView, StatusBar
    └── clawdash.tcss  BlackForest color palette
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run the app
clawdash
```

---

## License

MIT – [MiMi Tech AI UG](https://mimiai.de), Bad Liebenzell, Schwarzwald  
© 2026 MiMi Tech AI UG. All rights reserved.

---

*No cloud. No tracking. Straight from the Black Forest.* 🌲
