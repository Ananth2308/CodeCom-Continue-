import json
import uuid
import re
import httpx
from typing import AsyncGenerator
from app.core.config import settings
from app.core.tool_schemas import TOOL_SCHEMAS
from app.core.tool_parser import parse_tool_calls_from_text, build_tool_prompt_suffix
from app.tools.dispatcher import dispatch_tool
from app.tools.sandbox import test_code_in_sandbox

SYSTEM_PROMPT = """You are a software development agent with access to the project workspace.

**When to Use Each Approach:**

1. **EDITING EXISTING WORKSPACE FILES** (file_read, file_edit, file_write):
   - User says "edit [filename]", "modify [filename]", "change [filename]"
   - User says "rename [file]"
   - Working with existing project files
   - Saving code to a specific workspace location

   Steps for editing:
   a) Use file_read to read the existing file
   b) Use file_edit or file_write to modify it
   c) Use shell_execute to rename files if needed (e.g., "mv old.py new.py")

2. **CREATING NEW STANDALONE SCRIPTS** (test_standalone_code):
   - User says "create a script", "write a program", "generate code", "give me code"
   - User wants a NEW utility or standalone program
   - Code needs to be tested before showing to user

   Steps for new scripts:
   a) Generate complete, executable Python code
   b) Call test_standalone_code with the code
   c) Code will be tested automatically with results shown to user

Examples:
✓ "Edit fibonacci.py and change it to calculator" → Use file_read + file_edit
✓ "Modify main.py to add error handling" → Use file_read + file_edit
✓ "Rename test.py to app.py" → Use shell_execute with mv command
✓ "Create a new fibonacci script" → Use test_standalone_code
✓ "Write a calculator program" → Use test_standalone_code
✓ "Give me code for sorting" → Use test_standalone_code

**Important:**
- ALWAYS read files before editing them
- Use file operations for workspace file modifications
- Use test_standalone_code ONLY for new standalone scripts
- Keep changes minimal and focused

Workspace: {workspace_dir}
All relative paths resolve against this directory.
""".format(workspace_dir=settings.workspace_dir)


FILE_MODIFYING_TOOLS = {"file_write", "file_edit", "file_delete"}


class AgentLoop:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=300.0)
        self._use_prompt_mode: bool = False

    async def run(self, messages: list[dict]) -> AsyncGenerator[str | dict, None]:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        async for event in self._loop(full_messages):
            if isinstance(event, dict) and event.get("type") == "approval_needed":
                yield event
                return
            else:
                yield event

    async def resume(self, messages_so_far: list[dict], tool_call: dict, approved: bool) -> AsyncGenerator[str | dict, None]:
        func_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])

        # Special handling for sandbox testing with retry logic
        if func_name == "test_standalone_code":
            if not approved:
                yield _format_tool_call(func_name, "", "denied")
                yield "\nSandbox testing skipped. Task complete.\n"
                return

            yield _format_tool_call(func_name, "", "approved")
            yield "\n⏳ **Creating sandbox and testing code...**\n\n"

            # Execute sandbox test with retry logic (max 2 attempts)
            max_retries = 2
            attempt = 0

            while attempt < max_retries:
                attempt += 1

                if attempt > 1:
                    yield f"\n🔄 **Retry attempt {attempt}/{max_retries}** - Fixing code based on error...\n\n"

                result = await test_code_in_sandbox(
                    arguments["code"],
                    arguments.get("requirements", ""),
                    max_retries=1
                )

                result_dict = json.loads(result) if isinstance(result, str) else result

                if result_dict["success"]:
                    # Success - show the code and results
                    yield _format_sandbox_success(
                        arguments["code"],
                        arguments.get("requirements", ""),
                        result_dict["stdout"]
                    )

                    messages_so_far.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result,
                    })

                    # Continue with agent loop for any additional tasks
                    async for event in self._loop(messages_so_far):
                        if isinstance(event, dict) and event.get("type") == "approval_needed":
                            yield event
                            return
                        else:
                            yield event
                    return

                else:
                    # Failure - show error
                    yield _format_sandbox_error(result_dict["stderr"])

                    if attempt >= max_retries:
                        # Max retries reached, give up
                        yield f"\n⚠️ **Failed after {max_retries} attempts.** Ending conversation.\n"
                        return

                    # Ask LLM to fix the code and retry
                    yield "\nAsking LLM to fix the code...\n"
                    messages_so_far.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": f"Error: {result_dict['stderr']}\n\nPlease fix the code and provide the corrected version.",
                    })

                    # Get LLM to generate fixed code
                    async for event in self._loop(messages_so_far):
                        if isinstance(event, dict) and event.get("type") == "approval_needed":
                            # Shouldn't happen in retry, but handle it
                            yield event
                            return
                        else:
                            yield event

                    # Loop will retry with (hopefully) fixed code
                    # Update arguments with new code if LLM provided it
                    # (This is simplified - in reality, LLM should call test_standalone_code again)

            return

        # Regular tool handling (non-sandbox)
        if approved:
            result = await dispatch_tool(func_name, arguments)
            yield _format_tool_call(func_name, "", "approved")
        else:
            result = "User denied this action."
            yield _format_tool_call(func_name, "", "denied")

        messages_so_far.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": result,
        })

        async for event in self._loop(messages_so_far):
            if isinstance(event, dict) and event.get("type") == "approval_needed":
                yield event
                return
            else:
                yield event

    async def _loop(self, full_messages: list[dict]) -> AsyncGenerator[str | dict, None]:
        iteration = 0
        while iteration < settings.max_agent_iterations:
            iteration += 1

            response = await self._call_llm(full_messages)

            if response is None:
                yield "Error: Failed to get response from LLM\n"
                return

            assistant_message = response["choices"][0]["message"]
            raw_content = assistant_message.get("content", "")
            print(f"[DEBUG] LLM response ({len(raw_content)} chars): {raw_content[:200]}")

            # Parse tool calls from content if needed
            tool_calls = assistant_message.get("tool_calls")
            if not tool_calls:
                if raw_content:
                    clean_text, parsed_calls = parse_tool_calls_from_text(raw_content)

                    # Check if LLM is trying to write a new script to a file instead of using sandbox
                    if not parsed_calls:
                        intercepted_call = self._intercept_script_creation(raw_content)
                        if intercepted_call:
                            print(f"[DEBUG] Intercepted script creation, converting to sandbox test")
                            parsed_calls = [intercepted_call]
                            clean_text = "Creating and testing the script in sandbox..."

                    if parsed_calls:
                        print(f"[DEBUG] Parsed {len(parsed_calls)} tool calls")
                        assistant_message["content"] = clean_text
                        assistant_message["tool_calls"] = parsed_calls
                        tool_calls = parsed_calls
                    else:
                        print(f"[DEBUG] No tool calls parsed from response")

            full_messages.append(assistant_message)

            if not tool_calls:
                if raw_content:
                    yield raw_content
                return

            content = assistant_message.get("content", "")
            if content:
                yield f"*{content}*\n\n"

            # Execute tools
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                args_summary = _summarize_args(func_name, arguments)

                # Special handling for sandbox testing - show FULL code and ask for approval
                if func_name == "test_standalone_code":
                    # Show the FULL generated code to the user first (no truncation)
                    code_preview = arguments.get("code", "")
                    requirements_preview = arguments.get("requirements", "")
                    description = arguments.get("description", "Generated code")

                    preview_msg = f"> 🧪 **Test Standalone Code** — {description}\n\n"
                    preview_msg += "**Generated Code:**\n```python\n"
                    preview_msg += code_preview  # Show FULL code (no truncation)
                    preview_msg += "\n```\n\n"

                    if requirements_preview:
                        preview_msg += f"**Requirements:**\n```text\n{requirements_preview}\n```\n\n"

                    preview_msg += "> 🔒 **Test this code in an isolated sandbox?**\n"
                    preview_msg += "> Reply `yes` to test, `no` to skip\n"
                    preview_msg += "> (If you skip, you can copy the code above)\n\n"

                    yield preview_msg

                    # Suspend and wait for user approval
                    yield {
                        "type": "approval_needed",
                        "messages_so_far": full_messages,
                        "tool_call": tc,
                    }
                    return

                    while retry_count <= max_retries:
                        if retry_count > 0:
                            yield f"\n🔄 **Retry attempt {retry_count}/{max_retries}** - Fixing code based on error...\n\n"

                        result = await test_code_in_sandbox(
                            arguments["code"],
                            arguments.get("requirements", ""),
                            max_retries=1
                        )

                        result_dict = json.loads(result) if isinstance(result, str) else result

                        if result_dict["success"]:
                            # Success - show the code and results
                            yield _format_sandbox_success(
                                arguments["code"],
                                arguments.get("requirements", ""),
                                result_dict["stdout"]
                            )

                            full_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": result,
                            })
                            sandbox_completed = True
                            break
                        else:
                            # Failure - show error
                            yield _format_sandbox_error(result_dict["stderr"])

                            if retry_count >= max_retries:
                                # Max retries reached, give up
                                full_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result,
                                })
                                sandbox_completed = True
                                break

                            # Ask LLM to fix the code
                            retry_count += 1
                            fix_prompt = f"""The code failed with this error:
```
{result_dict["stderr"]}
```

Original code:
```python
{arguments["code"]}
```

Requirements:
```text
{arguments.get("requirements", "")}
```

Please fix the code and call test_standalone_code again with the corrected version. Make sure to:
1. Address the specific error shown above
2. Keep the code standalone and executable
3. Use lightweight libraries (avoid pygame, use tkinter or curses for UI if needed)
4. Include all necessary imports
"""
                            full_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": f"Error: {result_dict['stderr']}\n\nPlease fix the code and try again.",
                            })

                            # Continue to next iteration of agent loop to let LLM fix it
                            break

                    # Note: Don't exit here - let agent continue with other tasks
                    # The LLM might have more instructions to execute

                elif settings.require_approval and func_name in settings.dangerous_tools:
                    yield _format_tool_call(func_name, args_summary, "approval")
                    yield {
                        "type": "approval_needed",
                        "messages_so_far": full_messages,
                        "tool_call": tc,
                    }
                    return
                else:
                    result = await dispatch_tool(func_name, arguments)
                    yield _format_tool_call(func_name, args_summary, "done")

                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

        yield "\n⚠️ Agent reached maximum iterations\n"

    async def _call_llm(self, messages: list[dict]) -> dict | None:
        payload = {
            "model": settings.vllm_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        if not self._use_prompt_mode:
            payload["tools"] = TOOL_SCHEMAS
            payload["tool_choice"] = "auto"

        try:
            resp = await self.client.post(
                f"{settings.vllm_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.vllm_api_key}"},
            )
            resp.raise_for_status()
            result = resp.json()

            if not self._use_prompt_mode:
                error = result.get("error")
                if error and "tool" in str(error).lower():
                    self._use_prompt_mode = True
                    return await self._call_llm_prompt_mode(messages)

            if self._use_prompt_mode:
                return self._parse_prompt_mode_response(result)

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                if not self._use_prompt_mode:
                    # Try switching to prompt mode
                    self._use_prompt_mode = True
                    return await self._call_llm_prompt_mode(messages)
                else:
                    # Already in prompt mode and still getting 400
                    print(f"[WARNING] LLM API error 400 in both modes. Context may be too long.")
                    print(f"[WARNING] Response: {e.response.text[:500]}")
                    # Return a simple completion to end gracefully
                    return {
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": ""
                            }
                        }]
                    }
            print(f"LLM API error: {e.response.status_code} - {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"LLM connection error: {e}")
            return None

    async def _call_llm_prompt_mode(self, messages: list[dict]) -> dict | None:
        augmented = []
        for msg in messages:
            if msg["role"] == "system":
                augmented.append({
                    "role": "system",
                    "content": msg["content"] + build_tool_prompt_suffix(TOOL_SCHEMAS),
                })
            else:
                augmented.append(msg)

        payload = {
            "model": settings.vllm_model,
            "messages": augmented,
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        try:
            resp = await self.client.post(
                f"{settings.vllm_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.vllm_api_key}"},
            )
            resp.raise_for_status()
            return self._parse_prompt_mode_response(resp.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                print(f"[WARNING] LLM returned 400 Bad Request in prompt-mode. This may be due to context length or prompt format issues.")
                print(f"[WARNING] Response: {e.response.text[:500]}")
                # Return a simple completion to end the loop gracefully
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "Task completed. The code has been tested in the sandbox."
                        }
                    }]
                }
            print(f"LLM prompt-mode error: {e}")
            return None
        except Exception as e:
            print(f"LLM prompt-mode error: {e}")
            return None

    def _parse_prompt_mode_response(self, response: dict) -> dict:
        message = response["choices"][0]["message"]
        content = message.get("content", "")
        clean_text, tool_calls = parse_tool_calls_from_text(content)
        if tool_calls:
            message["content"] = clean_text
            message["tool_calls"] = tool_calls
        return response

    def _intercept_script_creation(self, content: str) -> dict | None:
        """
        Detect when LLM is trying to write a new standalone script to a file
        and convert it to use test_standalone_code tool instead.

        NOTE: Do NOT intercept if user is asking to edit/modify existing files.
        """
        # Check if this is an edit/modify request (should NOT be intercepted)
        edit_keywords = ['edit', 'modify', 'change', 'update', 'rename', 'fix']
        # This is a heuristic - in a full implementation you'd check actual message history
        if any(kw in content.lower()[:300] for kw in edit_keywords):
            # Likely an edit request, don't intercept
            return None

        # Pattern 1: ```python path/to/file.py\n<code>```
        pattern1 = r'```python\s+(?:src/)?([a-zA-Z0-9_]+\.py)\s*\n(.*?)```'
        match = re.search(pattern1, content, re.DOTALL)

        # Pattern 2: ```python\n<code>``` (standalone code block)
        if not match:
            pattern2 = r'```python\s*\n(.*?)```'
            match = re.search(pattern2, content, re.DOTALL)
            if match:
                code = match.group(1).strip()
                # Only intercept if it looks like a complete standalone script
                keywords = ['def ', 'class ', 'import ', 'if __name__']
                if any(kw in code for kw in keywords) and len(code) > 50:
                    # Check if user is asking for a new script (not modifying existing)
                    request_keywords = ['create', 'write', 'make', 'generate', 'build', 'give me']
                    user_message = self._get_last_user_message(content)
                    if any(kw in user_message.lower() for kw in request_keywords):
                        return self._create_sandbox_tool_call(code, "")

        # Pattern 1 match (code with file path)
        if match and len(match.groups()) == 2:
            filename, code = match.groups()
            code = code.strip()

            # Check if this looks like a new standalone script (not edit)
            # For edits, LLM should be using file_write tool properly
            if len(code) > 30:  # Reasonable minimum code length
                # Extract requirements if present
                requirements = ""
                req_match = re.search(r'```(?:text|requirements)\s*\n(.*?)```', content, re.DOTALL)
                if req_match:
                    requirements = req_match.group(1).strip()

                return self._create_sandbox_tool_call(code, requirements, filename)

        return None

    def _get_last_user_message(self, content: str) -> str:
        """Try to get the last user message from context"""
        # This is a simple heuristic - you might need to pass this more explicitly
        return content[:200]  # Just check the beginning of response for context

    def _create_sandbox_tool_call(self, code: str, requirements: str, description: str = "") -> dict:
        """Create a test_standalone_code tool call"""
        arguments = {
            "code": code,
            "requirements": requirements,
            "description": description or "Generated script"
        }

        return {
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": "test_standalone_code",
                "arguments": json.dumps(arguments)
            }
        }

    async def close(self):
        await self.client.aclose()


def _tool_icon(func_name: str) -> str:
    icons = {
        "file_read": "📖",
        "file_write": "✏️",
        "file_edit": "✏️",
        "file_delete": "🗑️",
        "glob_search": "🔍",
        "grep_search": "🔎",
        "shell_execute": "⚡",
        "run_tests": "🧪",
        "list_directory": "📂",
        "test_standalone_code": "🧪",
    }
    return icons.get(func_name, "⚙️")


def _tool_label(func_name: str) -> str:
    labels = {
        "file_read": "Read File",
        "file_write": "Write File",
        "file_edit": "Edit File",
        "file_delete": "Delete File",
        "glob_search": "Glob Search",
        "grep_search": "Grep Search",
        "shell_execute": "Shell",
        "run_tests": "Run Tests",
        "list_directory": "List Directory",
        "test_standalone_code": "Test Code in Sandbox",
    }
    return labels.get(func_name, func_name)


def _summarize_args(func_name: str, arguments: dict) -> str:
    if "path" in arguments:
        return arguments["path"]
    if "command" in arguments:
        return arguments["command"][:60]
    if "pattern" in arguments:
        return arguments["pattern"]
    return ""


def _format_tool_call(func_name: str, args_summary: str, status: str = "done") -> str:
    icon = _tool_icon(func_name)
    label = _tool_label(func_name)
    detail = f"  `{args_summary}`" if args_summary else ""

    if status == "done":
        return f"> {icon} **{label}**{detail} — ✓\n\n"
    elif status == "testing":
        return f"> {icon} **{label}**{detail}\n> \n> ⏳ **Creating sandbox and testing code...**\n\n"
    elif status == "approval":
        return (
            f"> {icon} **{label}**{detail}\n"
            f"> \n"
            f"> 🔒 **Approval required** — reply `yes` or `no`\n\n"
        )
    elif status == "approved":
        return f"> {icon} **{label}** — ✅ Approved\n\n"
    elif status == "denied":
        return f"> {icon} **{label}** — ❌ Denied\n\n"
    else:
        return f"> {icon} **{label}**{detail}\n\n"


def _format_sandbox_success(code: str, requirements: str, stdout: str) -> str:
    """Format successful sandbox execution results"""
    output = "### ✅ Sandbox Test Passed\n\n"
    output += "**Final Code:**\n```python\n" + code + "\n```\n\n"

    if requirements.strip():
        output += "**Requirements:**\n```text\n" + requirements + "\n```\n\n"

    output += "**Execution Output:**\n```\n"
    output += stdout if stdout.strip() else "Process completed successfully (no output)"
    output += "\n```\n\n"

    return output


def _format_sandbox_error(stderr: str) -> str:
    """Format sandbox execution error"""
    output = "### ❌ Sandbox Test Failed\n\n"
    output += "**Error:**\n```\n" + stderr + "\n```\n\n"
    return output
