# Sandbox Testing Feature

## Overview

The dev-agent now includes **automatic sandbox testing** for standalone Python code. When the agent generates new scripts or utilities, it can automatically test them in an isolated environment and show the results to the user in real-time.

## How It Works

### Automatic Testing Flow

1. **User requests standalone code** (e.g., "Create a script that fetches data from an API")
2. **Agent generates code** and calls `test_standalone_code` tool
3. **Sandbox is created** - A temporary virtual environment is set up
4. **Code is tested** - The script runs in the isolated environment
5. **Results are shown** - User sees the output or errors in real-time
6. **Auto-retry on failure** - If code fails, the agent automatically fixes it (up to 2 retries)
7. **Success** - Final working code is presented to the user

### Key Features

- ✅ **No approval required** - Testing happens automatically without interrupting the user
- ✅ **Real-time visibility** - User sees sandbox creation, testing, and results as they happen
- ✅ **Automatic retry** - Failed code is automatically fixed and retested (max 2 retries)
- ✅ **Isolated environment** - Each test runs in a temporary virtual environment that's cleaned up afterwards
- ✅ **Mock credentials** - AWS and other credentials are mocked to prevent accidental charges
- ✅ **Timeout protection** - Tests are limited to 30 seconds to prevent hanging

## Tool Specification

### `test_standalone_code`

Tests standalone Python code in an isolated sandbox environment.

**Parameters:**
- `code` (required): The complete Python code to test (must be executable standalone)
- `requirements` (optional): Pip requirements, one per line (e.g., "requests\nflask\nboto3")
- `description` (optional): Brief description of what the code does

**Example Usage:**

```json
{
  "name": "test_standalone_code",
  "arguments": {
    "code": "import requests\n\nresponse = requests.get('https://api.github.com')\nprint(f'Status: {response.status_code}')",
    "requirements": "requests",
    "description": "Test GitHub API connectivity"
  }
}
```

## User Experience

### Successful Test

```
> 🧪 Test Code in Sandbox  `Test script`
> 
> ⏳ Creating sandbox and testing code...

### ✅ Sandbox Test Passed

**Final Code:**
```python
import requests

response = requests.get('https://api.github.com')
print(f'Status: {response.status_code}')
```

**Requirements:**
```text
requests
```

**Execution Output:**
```
Status: 200
```
```

### Failed Test (with Auto-Retry)

```
> 🧪 Test Code in Sandbox  `Test script`
> 
> ⏳ Creating sandbox and testing code...

### ❌ Sandbox Test Failed

**Error:**
```
ModuleNotFoundError: No module named 'requests'
```

🔄 **Retry attempt 1/2** - Fixing code based on error...

### ✅ Sandbox Test Passed

**Final Code:**
```python
import requests

response = requests.get('https://api.github.com')
print(f'Status: {response.status_code}')
```

**Requirements:**
```text
requests
```

**Execution Output:**
```
Status: 200
```
```

## Technical Implementation

### Components

1. **`app/tools/sandbox.py`**
   - `SandboxExecutor`: Core class that creates and manages temporary virtual environments
   - `test_code_in_sandbox()`: Main function that executes code with retry logic
   - `extract_code_and_requirements()`: Extracts code blocks from markdown

2. **`app/core/agent_loop.py`**
   - Enhanced tool execution logic with special handling for sandbox testing
   - Auto-retry mechanism that asks LLM to fix failed code
   - Streaming progress updates to the user

3. **`app/core/tool_schemas.py`**
   - Added `test_standalone_code` tool schema

4. **`app/tools/dispatcher.py`**
   - Routes sandbox testing calls to the sandbox module

### Sandbox Environment

Each test creates:
- Temporary directory: `sandbox_<session_id>_<random>`
- Virtual environment with `--system-site-packages` flag
- Mock environment variables (AWS credentials, SDL video driver, etc.)
- Automatic cleanup after execution

### Safety Features

- **Timeout**: 30 second execution limit
- **Isolation**: Runs in temporary directory, no access to workspace
- **Mock credentials**: AWS keys are mocked to prevent accidental usage
- **Package safety**: Uses `--prefer-binary` to avoid building from source
- **Error handling**: All errors are caught and reported gracefully

## Best Practices

### When to Use Sandbox Testing

✅ **Good use cases:**
- Creating new standalone scripts
- Testing API integrations
- Building CLI tools
- Generating utilities and helpers
- Prototyping new functionality

❌ **Not suitable for:**
- Modifying existing workspace files (use regular file_write/file_edit)
- Long-running services or daemons
- Code that requires user input
- GUI applications with heavy native dependencies (pygame)

### Writing Sandbox-Friendly Code

**Do:**
- Use lightweight libraries (requests, flask, boto3)
- For UI, use tkinter (built-in) or curses (terminal-based)
- Include all necessary imports
- Make code fully self-contained
- Add print statements to show progress

**Don't:**
- Use pygame or other SDL-based libraries (requires native compilation)
- Rely on external files from the workspace
- Expect user input (stdin)
- Run indefinitely without timeout handling

### Example Prompts

- "Create a script that fetches weather data from OpenWeatherMap API"
- "Write a CLI tool that validates JSON files"
- "Generate a script to calculate Fibonacci numbers"
- "Create a simple HTTP server that serves static files"
- "Build a script that processes CSV data and generates a report"

## Configuration

No additional configuration needed! The sandbox feature:
- Does not require approval (not in `dangerous_tools` list)
- Uses existing workspace directory setting for context
- Automatically manages temporary directories
- Cleans up after itself

## Limitations

1. **Python only** - Currently only supports Python code
2. **30 second timeout** - Tests must complete within 30 seconds
3. **Max 2 retries** - If code fails after 2 fix attempts, it stops
4. **No workspace access** - Sandbox cannot read/write workspace files
5. **Limited to standalone code** - Cannot test code that depends on workspace context

## Future Enhancements

Potential improvements:
- Support for other languages (Node.js, Go, etc.)
- Configurable timeout and retry limits
- Option to save successful sandbox code to workspace
- Docker-based sandboxes for even better isolation
- Support for multi-file projects in sandbox
- Integration testing with mock databases
