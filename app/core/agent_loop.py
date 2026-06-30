import json
import httpx
from typing import AsyncGenerator
from app.core.config import settings
from app.core.tool_schemas import TOOL_SCHEMAS
from app.core.tool_parser import parse_tool_calls_from_text, build_tool_prompt_suffix
from app.tools.dispatcher import dispatch_tool

SYSTEM_PROMPT = """You are a software development agent with access to the project workspace.
You can read, write, and edit files, search the codebase, run shell commands, and execute tests.

Always write code to files using file_write or file_edit.
Read files before editing them.
Keep changes minimal and focused.

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

                if settings.require_approval and func_name in settings.dangerous_tools:
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
            if e.response.status_code == 400 and not self._use_prompt_mode:
                self._use_prompt_mode = True
                return await self._call_llm_prompt_mode(messages)
            print(f"LLM API error: {e.response.status_code} - {e.response.text}")
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
