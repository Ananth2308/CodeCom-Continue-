# Sandbox Testing - Quick Start Guide

## What is Sandbox Testing?

Automatic testing of standalone Python code in isolated environments with:
- ✅ **No approval needed** - Runs automatically
- ✅ **Real-time visibility** - See testing progress
- ✅ **Auto-retry** - Failed code is fixed automatically (up to 2 attempts)
- ✅ **Safe** - Runs in temporary isolated environment

## Quick Examples

### Example 1: Simple Request
**You ask:** "Create a script that prints hello world"

**Agent does:**
1. Generates Python code
2. Tests it in sandbox automatically
3. Shows you the working code + output

### Example 2: With Dependencies
**You ask:** "Create a script that fetches weather data from OpenWeatherMap"

**Agent does:**
1. Generates code with `requests` library
2. Creates virtual environment
3. Installs requirements
4. Tests the code
5. Shows you working code + output

### Example 3: Auto-Fix on Error
**You ask:** "Create a fibonacci calculator"

**Agent does:**
1. Generates code
2. Tests it → finds an error
3. **Automatically fixes the error**
4. Tests again → success!
5. Shows you the fixed working code

## How to Use

### Via Continue.dev

1. Start dev-agent:
   ```bash
   cd dev-agent
   python run.py
   ```

2. In Continue.dev, select "CodeCom Agent" model

3. Request standalone code:
   ```
   Create a script that [your task]
   ```

### Via API

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dev-agent",
    "stream": true,
    "messages": [{
      "role": "user", 
      "content": "Create a script that generates random passwords"
    }]
  }'
```

## What You'll See

### During Testing:
```
> 🧪 Test Code in Sandbox  `Description`
> 
> ⏳ Creating sandbox and testing code...
```

### On Success:
```
### ✅ Sandbox Test Passed

**Final Code:**
```python
[your code]
```

**Requirements:**
```text
[dependencies]
```

**Execution Output:**
```
[program output]
```
```

### On Failure with Auto-Fix:
```
### ❌ Sandbox Test Failed

**Error:**
```
[error message]
```

🔄 **Retry attempt 1/2** - Fixing code based on error...

### ✅ Sandbox Test Passed
[shows fixed code + output]
```

## Best Practices

### ✅ Good Requests:
- "Create a script that..."
- "Write a utility to..."
- "Generate a program that..."
- "Build a CLI tool for..."

### ❌ Not Suitable For:
- Modifying existing workspace files (use regular file operations)
- Long-running servers (30s timeout)
- Complex GUI apps with native dependencies

## Tips

1. **Be specific** - The more details you give, the better the code
2. **Trust the process** - If code fails, agent will auto-fix it
3. **Check the output** - Review execution results to verify behavior
4. **Save if needed** - Ask agent to save working code to workspace if you want to keep it

## Troubleshooting

### "Execution timeout"
- Code took longer than 30 seconds
- Ask for optimization or simpler approach

### "Pip installation failed"
- Package might not exist or have wrong name
- Agent will usually auto-fix this

### "Permission denied" (Windows)
- Usually auto-handled by using system Python
- If persists, run as administrator

## Configuration

No configuration needed! It works out of the box.

Optional: Adjust in `.env` if needed:
```env
# These affect sandbox behavior indirectly
AGENT_MAX_AGENT_ITERATIONS=25  # Total agent iterations
```

## Learn More

- Full documentation: [SANDBOX_FEATURE.md](SANDBOX_FEATURE.md)
- Examples: [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md)
- Implementation details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Test it: `python test_sandbox.py`

## Quick Commands

```bash
# Start the agent
cd dev-agent
python run.py

# Test sandbox directly
python test_sandbox.py

# Run with custom workspace
dev-agent --workspace /path/to/project

# Check health
curl http://localhost:8080/health
```

## Example Prompts to Try

1. "Create a script that generates QR codes"
2. "Write a JSON validator CLI tool"
3. "Build a password strength checker"
4. "Create a script that analyzes CSV files"
5. "Generate a simple HTTP server"
6. "Write a markdown to HTML converter"
7. "Build a file organizer script"
8. "Create a data visualization script with matplotlib"

---

**That's it!** Just ask for standalone code and the agent will automatically test it for you. 🚀
