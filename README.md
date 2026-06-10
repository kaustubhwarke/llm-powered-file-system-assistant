# LLM-Powered File System Assistant

An enterprise-grade Python application that exposes a sandboxed file system to a
Large Language Model as a set of callable tools, and runs a complete tool-use
agent loop so the LLM can autonomously read, search, write, and list files in
response to natural-language requests.

Implemented as the assignment **LLM-Powered File System Assistant**:

- **Part A (60%)** — Core file system tools in `fs_tools.py`
- **Part B (40%)** — LLM integration in `llm_file_assistant.py`

---

## Highlights

- **Two LLM providers** — pluggable OpenAI *and* Anthropic backends behind a
  single abstract interface; swap with one env var.
- **Sandboxed I/O** — every path is resolved against `FS_ROOT`; path-traversal
  and absolute-path escapes are rejected with `PathSecurityError`.
- **Multi-format reads** — `.txt`, `.md`, `.pdf` (pypdf), `.docx` (python-docx)
  with encoding fallback for text and graceful errors for corrupt/encrypted files.
- **Typed contracts everywhere** — Pydantic models validate every tool input
  and shape every tool result; the same models generate the JSON schemas
  delivered to the LLM.
- **Multi-turn tool loop** — handles parallel tool calls, error recovery, and
  is hard-capped by `AGENT_MAX_ITERATIONS` to prevent runaway billing.
- **Structured logging** — `structlog` JSON-ish event log on every tool call.
- **Rich CLI** — `ask`, `chat`, and `tools` sub-commands with optional
  tool-call trace.
- **53 unit tests** — fs tools (security, format support, errors), registry
  dispatch, agent loop (with a deterministic fake provider), and provider
  schema translation for both OpenAI and Anthropic.

---

## Project layout

```
llm-powered-file-system-assistant/
├── src/llm_file_assistant/
│   ├── __init__.py
│   ├── __main__.py                 # python -m llm_file_assistant
│   ├── cli.py                      # Typer CLI (ask / chat / tools)
│   ├── config.py                   # pydantic-settings configuration
│   ├── exceptions.py               # custom exception hierarchy
│   ├── fs_tools.py                 # PART A — the four required tools
│   ├── llm_file_assistant.py       # PART B — FileSystemAssistant agent
│   ├── logging_config.py           # structlog setup
│   ├── schemas.py                  # Pydantic I/O models + tool descriptors
│   ├── tools_registry.py           # name -> callable + schema dispatcher
│   └── providers/
│       ├── base.py                 # provider-neutral interfaces
│       ├── factory.py              # selects provider from settings
│       ├── openai_provider.py      # OpenAI chat.completions.tools
│       └── anthropic_provider.py   # Anthropic messages + tool_use
├── tests/
│   ├── conftest.py
│   ├── test_fs_tools.py            # 27 tests
│   ├── test_tools_registry.py      # 8 tests
│   ├── test_agent.py               # 7 tests
│   └── test_provider_translation.py# 8 tests (mocked SDK calls)
├── scripts/
│   └── generate_sample_resumes.py  # regenerates data/resumes/*
├── data/
│   └── resumes/                    # 10 dummy resumes (txt/docx/pdf)
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.10+
- A valid API key for either OpenAI **or** Anthropic

---

## Setup

```bash
# 1. Clone and enter
git clone <repo-url>
cd llm-powered-file-system-assistant

# 2. Create a virtualenv (recommended)
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux

# 3. Install runtime deps
pip install -r requirements.txt

# 4. Make the package importable as `llm-fs` (editable install)
pip install -e .

# 5. Configure
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
# then edit .env and add your API key
```

### Environment variables

| Variable               | Default              | Description                                      |
| ---------------------- | -------------------- | ------------------------------------------------ |
| `LLM_PROVIDER`         | `openai`             | `openai` or `anthropic`                          |
| `OPENAI_API_KEY`       | —                    | required when `LLM_PROVIDER=openai`              |
| `OPENAI_MODEL`         | `gpt-4o-mini`        | any tool-calling-capable OpenAI model            |
| `ANTHROPIC_API_KEY`    | —                    | required when `LLM_PROVIDER=anthropic`           |
| `ANTHROPIC_MODEL`      | `claude-sonnet-4-5`  | any Anthropic Messages tool-use-capable model    |
| `FS_ROOT`              | `./data`             | sandbox root; all FS ops are restricted here     |
| `FS_MAX_FILE_BYTES`    | `26214400` (25 MB)   | hard cap on single-file read & write             |
| `LOG_LEVEL`            | `INFO`               | `DEBUG` / `INFO` / `WARNING` / `ERROR`           |
| `AGENT_MAX_ITERATIONS` | `10`                 | safety cap on the tool-use loop                  |

---

## Usage

### Generate sample resumes (one time)

```bash
python scripts/generate_sample_resumes.py
```

This populates `data/resumes/` with 10 dummy resumes — 4 `.txt`, 3 `.docx`,
3 `.pdf` — covering a realistic mix of engineering roles.

### One-shot question

```bash
llm-fs ask "Read all resumes in the resumes folder and summarize each"
llm-fs ask "Find resumes mentioning Python experience"
llm-fs ask "Create a summary file at summaries/alice.md for resumes/alice_johnson.txt"
```

Add `--trace` to see every tool call the model made:

```bash
llm-fs ask --trace "Which candidates list Kubernetes?"
```

### Interactive chat

```bash
llm-fs chat            # add --trace to see tool calls each turn
```

### Inspect registered tools and configuration

```bash
llm-fs tools
```

### Module form (no install needed)

```bash
python -m llm_file_assistant ask "list all PDF resumes"
```

---

## The four core tools (Part A)

All four functions live in `src/llm_file_assistant/fs_tools.py`, take simple
arguments, return JSON-serializable dictionaries, and never raise on expected
I/O failures — errors are reported as `{"status": "error", "error": "...",
"error_type": "..."}` so the LLM can observe and recover.

### `read_file(filepath: str) -> dict`

Reads `.txt`, `.md`, `.pdf`, or `.docx` from inside the sandbox. PDFs are
parsed via `pypdf`; DOCX via `python-docx` (paragraphs *and* tables). Returns:

```json
{
  "status": "success",
  "content": "...",
  "metadata": {
    "name": "alice_johnson.txt",
    "path": "resumes/alice_johnson.txt",
    "extension": ".txt",
    "size_bytes": 714,
    "modified_at": "2026-05-30T14:18:13+00:00"
  },
  "page_count": null
}
```

### `list_files(directory: str, extension: str | None = None) -> list`

Lists files (not subdirectories) inside `directory`, optionally filtered by
extension (with or without leading dot). Each entry includes name, path,
size, and UTC modified timestamp.

### `write_file(filepath: str, content: str) -> dict`

Writes UTF-8 text content to a file inside the sandbox, creating any missing
parent directories. Reports whether directories were created and whether an
existing file was overwritten. Refuses to write past `FS_MAX_FILE_BYTES`.

### `search_in_file(filepath: str, keyword: str, context_lines: int = 2) -> dict`

Case-insensitive substring search returning every matching line with N lines
of context on either side and the character offset of the match.

---

## The agent loop (Part B)

`FileSystemAssistant.run(prompt)` orchestrates the tool-use cycle:

```
user prompt
   │
   ▼
provider.start_conversation(system_prompt, user_prompt)
   │
   ▼
┌──────────────────────────── loop (≤ AGENT_MAX_ITERATIONS) ─────┐
│  turn = provider.send_turn(tools)                              │
│    if turn.tool_calls:                                         │
│        for call in turn.tool_calls:                            │
│            result = tools_registry.execute(call.name, args)    │
│        provider.submit_tool_results(results); continue         │
│    else:                                                       │
│        return AgentRunResult(text=turn.text, ...)              │
└────────────────────────────────────────────────────────────────┘
```

Tool results are JSON-serialized and fed back in the next turn. The provider
layer translates the registry's provider-neutral `ToolDescriptor` objects
into OpenAI's `tools=[{type:"function", ...}]` format or Anthropic's
`tools=[{name, input_schema, ...}]` format. The same code paths above work
unchanged on either provider.

---

## Security model

| Threat                        | Mitigation                                          |
| ----------------------------- | --------------------------------------------------- |
| Path traversal (`../etc`)     | Every path is `resolve()`d and verified to be inside `FS_ROOT` |
| Absolute path escape          | Same — `Path.relative_to(root)` raises `ValueError`, mapped to `PathSecurityError` |
| Unbounded reads (DoS)         | `FS_MAX_FILE_BYTES` enforced before parsing         |
| Unbounded writes              | Same cap applied to the encoded UTF-8 payload       |
| Untrusted extensions          | Reads restricted to a known allow-list              |
| Encrypted / malformed PDFs    | Reported as `FileParseError`, not raised            |
| Infinite tool-call loops      | `AGENT_MAX_ITERATIONS` (default 10)                 |
| Secret leakage                | API keys read only from `.env` / env; `.env` git-ignored |

---

## Testing

```bash
# install dev deps
pip install pytest pytest-cov pytest-mock

# run the suite
pytest

# with coverage
pytest --cov=llm_file_assistant --cov-report=term-missing
```

Current results: **53 passing tests, 73% line coverage** (98%+ on the agent
loop, schemas, registry; remaining lines are defensive branches and the CLI
glue).

If a system-wide pytest plugin (e.g. `deepeval`) interferes with collection,
disable autoload:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -p pytest_cov \
  -o addopts="--cov=llm_file_assistant --cov-report=term-missing"
```

---

## Programmatic API

The package can be embedded in any Python service:

```python
from llm_file_assistant import (
    FileSystemAssistant,
    read_file, list_files, write_file, search_in_file,
)

# Tools directly
print(list_files("resumes", extension=".pdf"))
print(read_file("resumes/alice_johnson.txt"))

# Agent end-to-end
assistant = FileSystemAssistant()
result = assistant.run("Find resumes mentioning Kubernetes and write a shortlist")
print(result.text)                     # final assistant message
print(len(result.tool_invocations))    # how many tools it ran
print(result.elapsed_seconds)          # wall time
```

---

## Recording the demo video

The `scripts/demo.py` script is a turnkey walkthrough designed to be
screen-recorded:

```bash
# narrated mode — pauses between every step so you can talk through them
python scripts/demo.py

# straight-through mode — no pauses, useful for a clean re-take
python scripts/demo.py --auto

# hide the tool-call trace tables if you want a tidier video
python scripts/demo.py --no-trace
```

The script runs in two clearly-labeled sections:

1. **Part A** — calls each of the four `fs_tools` functions directly,
   showing inputs, outputs, and a security check (path-traversal rejection).
2. **Part B** — runs the LLM agent against the three example queries from
   the assignment brief, with full tool-call traces.

A typical recording with narration takes roughly 2–3 minutes — use
Windows Game Bar (`Win + G`), OBS, ShareX, or Loom to capture.

## Submission checklist

- [x] Source code with documentation — `src/llm_file_assistant/**`, docstrings on every public function
- [x] `requirements.txt` with pinned dependencies
- [x] 10 dummy resume files in `data/resumes/` (mix of `.txt`, `.docx`, `.pdf`)
- [x] `README.md` with setup and usage instructions (this file)
- [x] Demo runner ready (`scripts/demo.py`) — record screen while it runs

---

## License

MIT — see `pyproject.toml` for author/contact metadata.
