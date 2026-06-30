# CodeCom - Local AI Coding Agent

A self-hosted AI coding agent that connects to a remote vLLM instance and exposes an OpenAI-compatible API. Use it with **Continue.dev**, **VS Code**, or any tool that speaks the OpenAI chat completions protocol. The agent autonomously reads, writes, edits, searches, and runs commands in your local workspace — powered by your own GPU.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Tools Reference](#tools-reference)
- [How It Works](#how-it-works)
- [API Endpoints](#api-endpoints)
- [Approval System](#approval-system)
- [Tool Call Parsing](#tool-call-parsing)
- [Project Structure](#project-structure)
- [Extending with Custom Tools](#extending-with-custom-tools)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

CodeCom is a lightweight **agentic coding proxy** that sits between your IDE (or any OpenAI-compatible client) and a vLLM-served model. It intercepts chat completions, executes tool calls locally on your machine, and loops until the task is complete — all without sending your code to third-party APIs.

```
┌─────────────┐       HTTP        ┌─────────────┐       HTTP        ┌─────────────┐
│  Continue   │  ───────────────► │   CodeCom   │  ───────────────► │    vLLM     │
│  (VS Code)  │  ◄─────────────  │   (Proxy)   │  ◄─────────────  │  (EC2/GPU)  │
└─────────────┘   SSE Stream      └──────┬──────┘   Chat API        └─────────────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │  Your Local │
                                  │  Workspace  │
                                  └─────────────┘
```

---

## Architecture

```
app/
├── main.py              # FastAPI server — OpenAI-compatible /v1/chat/completions
├── cli.py               # CLI entry point (dev-agent command)
├── core/
│   ├── config.py        # Settings via pydantic-settings (.env support)
│   ├── agent_loop.py    # Core agent loop — LLM ↔ tool execution cycle
│   ├── tool_parser.py   # Multi-format tool call parser (native, Qwen, Continue)
│   └── tool_schemas.py  # OpenAI-format tool/function schemas
└── tools/
    ├── dispatcher.py    # Routes tool calls to implementations
    ├── filesystem.py    # File read/write/edit/delete/search/glob
    └── shell.py         # Shell execution and test runner
```

---

## Features

- **OpenAI-compatible API** — Drop-in replacement; works with Continue.dev, Open Interpreter, or `curl`
- **Full agentic loop** — The model calls tools, gets results, and iterates until done (up to 25 iterations)
- **9 built-in tools** — File I/O, glob/grep search, shell execution, multi-framework test runner
- **Approval system** — Dangerous operations (write, edit, delete, shell, tests) require user confirmation
- **Multi-format tool parsing** — Supports native OpenAI tool calls, Qwen `<tool_call>` format, Continue `TOOL_NAME:` format, and raw JSON blocks
- **Streaming SSE** — Real-time streamed responses, same format as OpenAI
- **Prompt-mode fallback** — If the model doesn't support native tool calling, falls back to prompt-based tool use
- **Configurable via `.env`** — All settings controlled through environment variables
- **Workspace sandboxing** — All file operations resolve relative to a configured workspace directory
- **Auto test framework detection** — Detects pytest, jest, mocha, go test, and cargo test

---

## Requirements

- **Python** 3.10+
- **A running vLLM instance** serving a code-capable model (e.g., Qwen3-Coder-30B, CodeLlama, DeepSeek-Coder)
- **Network access** from your machine to the vLLM server

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Ananth2308/CodeCom-Continue-.git
cd CodeCom-Continue-
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -e .
```

Or without editable mode:

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your settings (see [Configuration](#configuration)).

---

## Configuration

All configuration is done through environment variables (or a `.env` file). Every variable is prefixed with `AGENT_`.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_VLLM_BASE_URL` | `http://localhost:8000/v1` | Base URL of your vLLM instance (OpenAI-compatible endpoint) |
| `AGENT_VLLM_API_KEY` | `EMPTY` | API key for vLLM (use `EMPTY` if no auth) |
| `AGENT_VLLM_MODEL` | `default` | Model name as registered in vLLM |
| `AGENT_PROXY_HOST` | `0.0.0.0` | Host the proxy server listens on |
| `AGENT_PROXY_PORT` | `8080` | Port the proxy server listens on |
| `AGENT_WORKSPACE_DIR` | `/home/ubuntu/workspace` | Root directory the agent can access |
| `AGENT_REQUIRE_APPROVAL` | `true` | Whether dangerous tools need user approval |
| `AGENT_MAX_AGENT_ITERATIONS` | `25` | Max tool-call loops before the agent stops |

### Example `.env`

```env
AGENT_VLLM_BASE_URL=http://54.123.45.67:8080/v1
AGENT_VLLM_API_KEY=EMPTY
AGENT_VLLM_MODEL=qwen3-coder-30b-awq4

AGENT_PROXY_HOST=0.0.0.0
AGENT_PROXY_PORT=8080

AGENT_WORKSPACE_DIR=C:\Users\YourName\Projects\my-project

AGENT_REQUIRE_APPROVAL=true
AGENT_MAX_AGENT_ITERATIONS=25
```

---

## Usage

### Start the agent server

```bash
dev-agent
```

Or with command-line overrides:

```bash
dev-agent --host 127.0.0.1 --port 9090 --workspace /path/to/project --vllm-url http://your-gpu:8080/v1
```

Or run directly:

```bash
python run.py
```

### Connect from Continue.dev

In your Continue config (`~/.continue/config.json`), add a model:

```json
{
  "models": [
    {
      "title": "CodeCom Agent",
      "provider": "openai",
      "model": "dev-agent",
      "apiBase": "http://localhost:8080/v1",
      "apiKey": "not-needed"
    }
  ]
}
```

### Use with curl

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dev-agent",
    "stream": true,
    "messages": [{"role": "user", "content": "Read the main.py file and explain what it does"}]
  }'
```

---

## Tools Reference

The agent has access to 9 built-in tools:

### File Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `file_read` | Read file contents with line numbers | `path` (required), `offset`, `limit` |
| `file_write` | Create or overwrite a file | `path` (required), `content` (required) |
| `file_edit` | Find-and-replace a unique string in a file | `path`, `old_string`, `new_string` (all required) |
| `file_delete` | Delete a file or directory | `path` (required), `recursive` |

### Search Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `glob_search` | Find files by glob pattern | `pattern` (required), `path` |
| `grep_search` | Regex search through file contents | `pattern` (required), `path`, `include`, `ignore_case` |
| `list_directory` | List files/dirs at a path | `path`, `recursive` |

### Execution

| Tool | Description | Parameters |
|------|-------------|------------|
| `shell_execute` | Run a shell command | `command` (required), `timeout`, `cwd` |
| `run_tests` | Run project tests | `test_path`, `framework`, `verbose` |

### Supported Test Frameworks

The `run_tests` tool auto-detects the test framework based on project files:

| Framework | Detection | Command |
|-----------|-----------|---------|
| pytest | `pyproject.toml` or `pytest.ini` exists | `python -m pytest` |
| jest | `package.json` with jest in test script | `npx jest` |
| mocha | `package.json` with mocha in test script | `npx mocha` |
| go | `go.mod` exists | `go test ./...` |
| cargo | `Cargo.toml` exists | `cargo test` |

---

## How It Works

### The Agent Loop

1. **User sends a message** via the OpenAI-compatible API
2. **System prompt is prepended** with workspace context and tool descriptions
3. **LLM is called** with the conversation + tool schemas
4. **If the LLM returns tool calls:**
   - Each tool call is parsed and validated
   - Dangerous tools pause for approval (if enabled)
   - Tool is executed locally and the result is appended to the conversation
   - Loop back to step 3
5. **If the LLM returns plain text:** Stream it to the client as the final response
6. **Safety cap:** After 25 iterations (configurable), the loop terminates

### Prompt-Mode Fallback

Not all models support native OpenAI function calling. When a model returns an error on tool-augmented requests, CodeCom automatically switches to **prompt mode**:

- Tool schemas are injected into the system prompt as formatted text
- The model outputs tool calls using the `<tool_call>` XML format
- CodeCom parses these from the response text and executes them identically

This happens transparently — no configuration needed.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat completions (streaming + non-streaming) |
| `GET` | `/v1/models` | List available models |
| `GET` | `/health` | Health check (returns workspace path) |

### Request Format

```json
{
  "model": "dev-agent",
  "stream": true,
  "messages": [
    {"role": "user", "content": "Your task here"}
  ]
}
```

### Response Format

Streaming responses follow the OpenAI SSE format:

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"dev-agent","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: [DONE]
```

---

## Approval System

When `AGENT_REQUIRE_APPROVAL=true`, the following tools require user confirmation before executing:

- `shell_execute` — Arbitrary command execution
- `file_write` — Creating/overwriting files
- `file_edit` — Modifying file contents
- `file_delete` — Deleting files/directories
- `run_tests` — Running test suites

### How approval works:

1. The agent streams a blockquote card showing the tool and its arguments
2. The response pauses, waiting for user input
3. The user's next message is interpreted as approval (`yes`, `y`, `approve`, `ok`, `sure`, `go`, `do it`) or denial (anything else)
4. On denial, the user's message is treated as a new prompt instead

---

## Tool Call Parsing

CodeCom supports multiple tool call formats to work with different models:

### Format 1: Native OpenAI Tool Calls
Models that support `tools` parameter natively (e.g., via vLLM's tool calling support).

### Format 2: Qwen-style XML
```xml
<tool_call>
<function=file_read>
<parameter=path>src/main.py</parameter>
</function>
</tool_call>
```

### Format 3: Continue-style Blocks
```
```tool
TOOL_NAME: readFile
BEGIN_ARG: filePath
src/main.py
END_ARG
```​
```

### Format 4: Raw JSON
```json
{"name": "file_read", "arguments": {"path": "src/main.py"}}
```

All formats are detected automatically. The parser tries them in order and uses the first successful match.

---

## Project Structure

```
CodeCom-Continue-/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, SSE streaming, session management
│   ├── cli.py               # CLI entry point with argparse
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic settings (env vars + .env file)
│   │   ├── agent_loop.py    # LLM ↔ tool execution loop
│   │   ├── tool_parser.py   # Multi-format parser for tool calls
│   │   └── tool_schemas.py  # OpenAI function-calling schemas
│   └── tools/
│       ├── __init__.py
│       ├── dispatcher.py    # Tool name → implementation router
│       ├── filesystem.py    # File and search operations
│       └── shell.py         # Command execution and test runner
├── run.py                   # Direct run entry point
├── pyproject.toml           # Package metadata and dependencies
├── requirements.txt         # Pip requirements
├── .env.example             # Example environment configuration
└── README.md                # This file
```

---

## Extending with Custom Tools

To add a new tool:

### 1. Define the schema in `app/core/tool_schemas.py`

```python
{
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "What this tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "..."},
            },
            "required": ["param1"],
        },
    },
},
```

### 2. Implement the tool

Create a function in an existing tools file or a new one under `app/tools/`:

```python
def my_tool(param1: str) -> str:
    # Do something
    return "result"
```

### 3. Register in the dispatcher (`app/tools/dispatcher.py`)

```python
case "my_tool":
    return my_tool(arguments["param1"])
```

### 4. (Optional) Add display metadata in `agent_loop.py`

Add entries to `_tool_icon()` and `_tool_label()` for nice rendering.

---

## Troubleshooting

### Agent not connecting to vLLM

- Verify the vLLM server is running: `curl http://YOUR_IP:PORT/v1/models`
- Check `AGENT_VLLM_BASE_URL` includes `/v1`
- Ensure network/firewall allows the connection

### Tool calls not being parsed

- Check the debug output in the terminal for `[DEBUG] Parsed X tool calls`
- If you see `No tool calls parsed from response`, the model may not be formatting them correctly
- Try a different model or check if prompt-mode fallback is activating

### "Agent reached maximum iterations"

- Increase `AGENT_MAX_AGENT_ITERATIONS` in `.env`
- The model may be stuck in a loop — check the conversation for repetitive tool calls

### File permission errors

- Ensure `AGENT_WORKSPACE_DIR` points to a directory your user can read/write
- On Windows, use full paths (e.g., `C:\Users\Name\Projects\myproject`)

### Model returns errors with tools

- Some models don't support native tool calling — CodeCom will auto-fallback to prompt mode
- Check terminal for `LLM API error: 400` messages (this triggers the fallback)

---

## Recommended Models

CodeCom works best with code-specialized models served via vLLM:

| Model | Size | Notes |
|-------|------|-------|
| Qwen3-Coder-30B-AWQ | 30B (4-bit) | Excellent tool-calling, fits on single A10G |
| DeepSeek-Coder-V2-Lite | 16B | Good balance of speed and capability |
| CodeLlama-34B | 34B | Strong coding, needs native tool call support |
| Qwen2.5-Coder-32B | 32B | Very capable, supports function calling |

---

## License

MIT

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

*Built for developers who want AI coding assistance without sending their code to the cloud.*
