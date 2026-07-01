# CodeCom - Local AI Coding Agent with Sandbox Testing

A self-hosted AI coding agent that connects to a remote vLLM instance and exposes an OpenAI-compatible API. Use it with **Continue.dev**, **VS Code**, or any tool that speaks the OpenAI chat completions protocol. The agent autonomously reads, writes, edits, searches, runs commands, and **tests code in isolated sandboxes** — all powered by your own GPU, without sending code to third-party APIs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 🌟 Key Features

- **OpenAI-compatible API** — Drop-in replacement for Continue.dev, Open Interpreter, or any OpenAI client
- **Full agentic loop** — The model calls tools, gets results, and iterates until done (up to 25 iterations)
- **10 built-in tools** — File I/O, glob/grep search, shell execution, test runner, **sandbox testing**
- **🆕 Automatic sandbox testing** — Test standalone code in isolated environments with human-in-the-loop approval
- **Human-in-the-loop approval** — Review generated code before testing, with auto-retry on failure (max 2 attempts)
- **Multi-format tool parsing** — Supports native OpenAI, Qwen `<tool_call>`, Continue `TOOL_NAME:`, and JSON formats
- **Streaming SSE** — Real-time streamed responses with progress updates
- **Prompt-mode fallback** — Works with models that don't support native tool calling
- **Configurable via `.env`** — All settings controlled through environment variables
- **Workspace sandboxing** — All file operations resolve relative to a configured workspace directory
- **Auto test framework detection** — Detects pytest, jest, mocha, go test, and cargo test

---

## 📋 Table of Contents

- [Overview](#overview)
- [What's New - Sandbox Testing](#whats-new---sandbox-testing)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Tools Reference](#tools-reference)
- [Sandbox Testing Guide](#sandbox-testing-guide)
- [How It Works](#how-it-works)
- [API Endpoints](#api-endpoints)
- [Approval System](#approval-system)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

CodeCom is a lightweight **agentic coding proxy** that sits between your IDE and a vLLM-served model. It intercepts chat completions, executes tool calls locally on your machine, and loops until the task is complete.

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

## 🆕 What's New - Sandbox Testing

### Human-in-the-Loop Code Testing

When you ask the agent to create new standalone scripts, it now:

1. **Generates the code** and shows you the **full code** (not truncated)
2. **Asks for approval**: "Test this code in an isolated sandbox?"
3. **You decide**:
   - Reply `yes` → Tests in isolated environment, shows results
   - Reply `no` → Skips testing, you can copy the code
4. **Auto-retry**: If code fails, LLM fixes it automatically (max 2 attempts)
5. **Safe & Isolated**: Runs in temporary directory with mock credentials

### Example Flow

```
User: "create a fibonacci calculator"

Agent:
> 🧪 Test Standalone Code — Fibonacci calculator

**Generated Code:**
```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
```

> 🔒 Test this code in an isolated sandbox?
> Reply `yes` to test, `no` to skip
> (If you skip, you can copy the code above)

User: "yes"

Agent:
✅ Sandbox Test Passed

**Execution Output:**
```
F(0) = 0
F(1) = 1
F(2) = 1
F(3) = 2
...
```
```

See [SANDBOX_FEATURE.md](SANDBOX_FEATURE.md) for complete documentation.

---

## 🏗️ Architecture

```
app/
├── main.py              # FastAPI server — OpenAI-compatible /v1/chat/completions
├── cli.py               # CLI entry point (dev-agent command)
├── core/
│   ├── config.py        # Settings via pydantic-settings (.env support)
│   ├── agent_loop.py    # Core agent loop — LLM ↔ tool execution cycle
│   ├── tool_parser.py   # Multi-format tool call parser
│   └── tool_schemas.py  # OpenAI-format tool/function schemas
└── tools/
    ├── dispatcher.py    # Routes tool calls to implementations
    ├── filesystem.py    # File read/write/edit/delete/search/glob
    ├── shell.py         # Shell execution and test runner
    └── sandbox.py       # 🆕 Isolated sandbox testing
```

---

## 📦 Requirements

- **Python** 3.10+
- **A running vLLM instance** serving a code-capable model (e.g., Qwen3-Coder-30B, CodeLlama, DeepSeek-Coder)
- **Network access** from your machine to the vLLM server

---

## 🚀 Installation

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

## ⚙️ Configuration

All configuration is done through environment variables (or a `.env` file). Every variable is prefixed with `AGENT_`.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_VLLM_BASE_URL` | `http://localhost:8000/v1` | Base URL of your vLLM instance |
| `AGENT_VLLM_API_KEY` | `EMPTY` | API key for vLLM (use `EMPTY` if no auth) |
| `AGENT_VLLM_MODEL` | `default` | Model name as registered in vLLM |
| `AGENT_PROXY_HOST` | `0.0.0.0` | Host the proxy server listens on |
| `AGENT_PROXY_PORT` | `8080` | Port the proxy server listens on |
| `AGENT_WORKSPACE_DIR` | `/home/ubuntu/workspace` | Root directory the agent can access |
| `AGENT_REQUIRE_APPROVAL` | `true` | Whether dangerous tools need user approval |
| `AGENT_MAX_AGENT_ITERATIONS` | `25` | Max tool-call loops before the agent stops |

### Example `.env`

```env
# vLLM connection
AGENT_VLLM_BASE_URL=http://54.123.45.67:8000/v1
AGENT_VLLM_API_KEY=EMPTY
AGENT_VLLM_MODEL=qwen3-coder-30b-awq4

# Proxy settings
AGENT_PROXY_HOST=0.0.0.0
AGENT_PROXY_PORT=8080

# Workspace (Windows example)
AGENT_WORKSPACE_DIR=C:\Users\YourName\Projects\my-project

# Agent behavior
AGENT_REQUIRE_APPROVAL=true
AGENT_MAX_AGENT_ITERATIONS=25
```

---

## 🎮 Usage

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
    "messages": [{"role": "user", "content": "Create a script that calculates prime numbers"}]
  }'
```

---

## 🛠️ Tools Reference

The agent has access to 10 built-in tools:

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

### Execution & Testing

| Tool | Description | Parameters | Approval Required |
|------|-------------|------------|-------------------|
| `shell_execute` | Run a shell command | `command` (required), `timeout`, `cwd` | ✅ Yes |
| `run_tests` | Run project tests | `test_path`, `framework`, `verbose` | ✅ Yes |
| `test_standalone_code` | 🆕 Test standalone code in isolated sandbox | `code` (required), `requirements`, `description` | ✅ Yes (human-in-the-loop) |

> **🆕 New!** The `test_standalone_code` tool tests generated code in an isolated environment with human approval. Shows full code, user decides whether to test. Auto-retries on failure (max 2 attempts). See [Sandbox Testing Guide](#sandbox-testing-guide).

---

## 🧪 Sandbox Testing Guide

### When It's Used

Sandbox testing is **automatically triggered** when you ask to create new standalone scripts:

- ✅ "Create a fibonacci script"
- ✅ "Write a calculator program"
- ✅ "Generate code for prime numbers"
- ✅ "Make a script that fetches API data"

### When It's NOT Used

- ❌ Editing existing workspace files (uses `file_edit` instead)
- ❌ Modifying project code
- ❌ Just asking for explanations

### The Approval Process

1. **Agent generates code** → Shows you the **full code** (not truncated)
2. **Agent asks**: "Test this code in an isolated sandbox?"
3. **You decide**:
   - Reply `yes` → Runs in sandbox, shows results
   - Reply `no` → Skips testing, conversation ends
4. **If fails**: Auto-retry with LLM fix (max 2 attempts)
5. **If fails 2x**: "Failed after 2 attempts. Ending conversation."

### Safety Features

- ✅ Runs in temporary isolated directory
- ✅ Mock AWS credentials (prevents accidental charges)
- ✅ 30-second execution timeout
- ✅ Automatic cleanup after execution
- ✅ No access to workspace files
- ✅ Full code visibility before testing

### Example Commands

```bash
# Simple script
"create a script that prints hello world"

# With dependencies
"write a script that fetches GitHub API data"

# Complex logic
"generate a recursive fibonacci calculator"

# Data processing
"create a CSV parser that calculates averages"
```

See [SANDBOX_FEATURE.md](SANDBOX_FEATURE.md) for complete technical documentation and [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md) for more examples.

---

## 🔄 How It Works

### The Agent Loop

1. **User sends a message** via the OpenAI-compatible API
2. **System prompt is prepended** with workspace context and tool descriptions
3. **LLM is called** with the conversation + tool schemas
4. **If the LLM returns tool calls:**
   - Each tool call is parsed and validated
   - Dangerous tools pause for approval (if enabled)
   - **Sandbox testing shows full code and asks for approval**
   - Tool is executed locally and the result is appended to conversation
   - Loop back to step 3
5. **If the LLM returns plain text:** Stream it to the client as final response
6. **Safety cap:** After 25 iterations (configurable), the loop terminates

### Sandbox Testing Flow

```
User Request
    ↓
LLM Generates Code
    ↓
Show Full Code to User
    ↓
Ask: "Test in sandbox?" (yes/no)
    ↓
├─→ User says "no" → End (user can copy code)
│
└─→ User says "yes"
        ↓
    Create Temp Directory
        ↓
    Install Requirements (if any)
        ↓
    Execute Code (30s timeout)
        ↓
    ├─→ Success → Show results, continue
    │
    └─→ Failure
            ↓
        Attempt < 2?
            ↓
        ├─→ Yes → LLM fixes, retry
        │
        └─→ No → "Failed after 2 attempts", end
```

### Prompt-Mode Fallback

Not all models support native OpenAI function calling. When a model returns an error on tool-augmented requests, CodeCom automatically switches to **prompt mode**:

- Tool schemas are injected into the system prompt as formatted text
- The model outputs tool calls using the `<tool_call>` XML format
- CodeCom parses these from the response text and executes them identically

This happens transparently — no configuration needed.

---

## 📡 API Endpoints

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
    {"role": "user", "content": "Create a fibonacci calculator"}
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

## 🔐 Approval System

When `AGENT_REQUIRE_APPROVAL=true`, the following tools require user confirmation before executing:

### Dangerous Tools (Regular Approval)
- `shell_execute` — Arbitrary command execution
- `file_write` — Creating/overwriting files
- `file_edit` — Modifying file contents
- `file_delete` — Deleting files/directories
- `run_tests` — Running test suites

### Sandbox Testing (Human-in-the-Loop Approval)
- `test_standalone_code` — Shows **full code** and asks "Test in sandbox?"
  - User sees complete code before testing
  - Can copy code if they decline testing
  - Auto-retry on failure (max 2 attempts)

### How approval works:

1. The agent streams a card showing the tool and its arguments (or full code for sandbox)
2. The response pauses, waiting for user input
3. The user's next message is interpreted as:
   - Approval: `yes`, `y`, `approve`, `ok`, `sure`, `go`, `do it`
   - Denial: anything else (treated as new prompt)

---

## 📁 Project Structure

```
CodeCom-Continue-/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, SSE streaming, session management
│   ├── cli.py               # CLI entry point with argparse
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic settings (env vars + .env file)
│   │   ├── agent_loop.py    # LLM ↔ tool execution loop + sandbox integration
│   │   ├── tool_parser.py   # Multi-format parser for tool calls
│   │   └── tool_schemas.py  # OpenAI function-calling schemas
│   └── tools/
│       ├── __init__.py
│       ├── dispatcher.py    # Tool name → implementation router
│       ├── filesystem.py    # File and search operations
│       ├── shell.py         # Command execution and test runner
│       └── sandbox.py       # 🆕 Isolated sandbox testing
├── run.py                   # Direct run entry point
├── test_sandbox.py          # 🆕 Sandbox verification tests
├── pyproject.toml           # Package metadata and dependencies
├── requirements.txt         # Pip requirements
├── .env.example             # Example environment configuration
├── README.md                # This file
├── SANDBOX_FEATURE.md       # 🆕 Detailed sandbox documentation
├── EXAMPLE_USAGE.md         # 🆕 Sandbox usage examples
└── QUICKSTART_SANDBOX.md    # 🆕 Quick start guide
```

---

## 🐛 Troubleshooting

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

### Sandbox testing not triggering

- Make sure your request uses keywords like "create", "write", "generate", "make"
- If asking to edit existing files, it will use file operations instead
- Check system prompt in `app/core/agent_loop.py` if needed

### Sandbox timeout errors

- Code takes longer than 30 seconds to execute
- Simplify the code or optimize for performance
- Long-running services won't work (use for scripts only)

### Code not showing fully in Continue.dev

- This is a display issue with Continue.dev
- The full code is being sent, check the raw response
- Try using the API directly with curl to verify

---

## 🎨 Recommended Models

CodeCom works best with code-specialized models served via vLLM:

| Model | Size | Notes |
|-------|------|-------|
| Qwen3-Coder-30B-AWQ | 30B (4-bit) | ✅ Excellent tool-calling, fits on single A10G |
| DeepSeek-Coder-V2-Lite | 16B | Good balance of speed and capability |
| CodeLlama-34B | 34B | Strong coding, needs native tool call support |
| Qwen2.5-Coder-32B | 32B | Very capable, supports function calling |

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Install in development mode
pip install -e .

# Run tests
python test_sandbox.py

# Test locally
dev-agent --workspace /path/to/test/project
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [vLLM](https://github.com/vllm-project/vllm)
- Inspired by [Continue.dev](https://continue.dev/)

---

## 📚 Additional Documentation

- [SANDBOX_FEATURE.md](SANDBOX_FEATURE.md) - Complete sandbox testing documentation
- [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md) - Detailed usage examples
- [QUICKSTART_SANDBOX.md](QUICKSTART_SANDBOX.md) - Quick start guide for sandbox testing
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical implementation details

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/Ananth2308/CodeCom-Continue-/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Ananth2308/CodeCom-Continue-/discussions)

---

**Built for developers who want AI coding assistance without sending their code to the cloud.** 🚀

*Now with isolated sandbox testing for safer, more reliable code generation!* 🧪
