import json
import re
from typing import Optional


def parse_tool_calls_from_text(text: str) -> tuple[str, list[dict]]:
    """Parse tool calls from model output text. Supports multiple formats."""
    tool_calls = []
    clean_text = text

    # Format 1: Continue-style ```tool blocks
    tool_block_pattern = r"```tool\s*\n(.*?)```"
    tool_matches = re.findall(tool_block_pattern, text, re.DOTALL)
    if tool_matches:
        for i, match in enumerate(tool_matches):
            tc = _parse_continue_tool_call(match, f"call_{i}")
            if tc:
                tool_calls.append(tc)
        if tool_calls:
            clean_text = re.sub(tool_block_pattern, "", text, flags=re.DOTALL).strip()
            return clean_text, tool_calls

    # Format 2: <tool_call>...</tool_call> blocks (Qwen style)
    qwen_pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    qwen_matches = re.findall(qwen_pattern, text, re.DOTALL)
    if qwen_matches:
        for i, match in enumerate(qwen_matches):
            tc = _parse_qwen_tool_call(match, f"call_{i}")
            if tc:
                tool_calls.append(tc)
            else:
                parsed = _try_parse_json(match)
                if parsed:
                    tc = _normalize_tool_call(parsed, f"call_{i}")
                    if tc:
                        tool_calls.append(tc)
        clean_text = re.sub(qwen_pattern, "", text, flags=re.DOTALL).strip()
        if tool_calls:
            return clean_text, tool_calls

    # Format 3: JSON code block ```json\n{...}\n```
    json_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    json_matches = re.findall(json_block_pattern, text, re.DOTALL)
    for i, match in enumerate(json_matches):
        parsed = _try_parse_json(match)
        if parsed and _looks_like_tool_call(parsed):
            tc = _normalize_tool_call(parsed, f"call_{i}")
            if tc:
                tool_calls.append(tc)

    if tool_calls:
        clean_text = re.sub(json_block_pattern, "", text, flags=re.DOTALL).strip()
        return clean_text, tool_calls

    return clean_text, tool_calls


def build_tool_prompt_suffix(tool_schemas: list[dict]) -> str:
    """Build a system prompt suffix for models without native tool calling."""
    tools_desc = []
    for schema in tool_schemas:
        func = schema["function"]
        params = json.dumps(func["parameters"], indent=2)
        tools_desc.append(
            f"### {func['name']}\n{func['description']}\nParameters:\n```json\n{params}\n```"
        )

    return f"""
## Available Tools

To use a tool, output a tool call in this exact format:

<tool_call>
<function=tool_name>
<parameter=param1>value1</parameter>
<parameter=param2>value2</parameter>
</function>
</tool_call>

You may output text before and after tool calls. You can make multiple tool calls in one response.
After each tool call, you will receive the result. Continue calling tools until the task is complete.

{chr(10).join(tools_desc)}
"""


def _parse_continue_tool_call(text: str, call_id: str) -> Optional[dict]:
    """Parse Continue-style tool format:
    TOOL_NAME: name
    BEGIN_ARG: key
    value
    END_ARG
    """
    # Extract tool name
    name_match = re.search(r"TOOL_NAME:\s*(.+)", text)
    if not name_match:
        return None

    tool_name = name_match.group(1).strip()

    # Map Continue tool names to our tool names
    tool_name_map = {
        "ls": "list_directory",
        "readFile": "file_read",
        "writeFile": "file_write",
        "editFile": "file_edit",
        "deleteFile": "file_delete",
        "search": "grep_search",
        "grep": "grep_search",
        "glob": "glob_search",
        "exec": "shell_execute",
        "run": "shell_execute",
        "runTests": "run_tests",
    }
    mapped_name = tool_name_map.get(tool_name, tool_name)

    # Extract arguments
    arg_pattern = r"BEGIN_ARG:\s*(\w+)\s*\n(.*?)END_ARG"
    args = re.findall(arg_pattern, text, re.DOTALL)

    arguments = {}
    for key, value in args:
        key = key.strip()
        value = value.strip().strip('"')
        # Try to parse as JSON value
        try:
            arguments[key] = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            arguments[key] = value

    # Map Continue argument names to our argument names
    arg_name_map = {
        "dirPath": "path",
        "filePath": "path",
        "filepath": "path",
        "query": "pattern",
        "cmd": "command",
        "recursive": "recursive",
        "content": "content",
    }
    mapped_args = {}
    for k, v in arguments.items():
        mapped_key = arg_name_map.get(k, k)
        mapped_args[mapped_key] = v

    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": mapped_name,
            "arguments": json.dumps(mapped_args),
        },
    }


def _parse_qwen_tool_call(text: str, call_id: str) -> Optional[dict]:
    """Parse Qwen-style: <function=name><parameter=key>value</parameter>"""
    func_match = re.search(r"<function=([^>]+)>", text)
    if not func_match:
        return None

    func_name = func_match.group(1).strip()
    param_pattern = r"<parameter=([^>]+)>(.*?)(?:</parameter>|(?=<parameter=)|$)"
    params = re.findall(param_pattern, text, re.DOTALL)

    arguments = {}
    for key, value in params:
        key = key.strip()
        value = value.strip()
        try:
            arguments[key] = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            arguments[key] = value

    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": func_name,
            "arguments": json.dumps(arguments),
        },
    }


def _try_parse_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None


def _looks_like_tool_call(obj: dict) -> bool:
    return any(key in obj for key in ("tool", "function", "name", "tool_calls"))


def _normalize_tool_call(parsed: dict, call_id: str) -> Optional[dict]:
    name = parsed.get("name") or parsed.get("tool") or parsed.get("function")
    arguments = parsed.get("arguments") or parsed.get("params") or parsed.get("parameters") or {}

    if isinstance(name, dict):
        arguments = name.get("arguments", arguments)
        name = name.get("name")

    if not name or not isinstance(name, str):
        return None

    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments) if isinstance(arguments, dict) else str(arguments),
        },
    }
