import json
from app.tools.filesystem import (
    file_read, file_write, file_edit, file_delete,
    glob_search, grep_search, list_directory,
)
from app.tools.shell import shell_execute, run_tests
from app.tools.sandbox import test_code_in_sandbox


async def dispatch_tool(name: str, arguments: dict) -> str:
    try:
        match name:
            case "file_read":
                if "path" not in arguments:
                    return "Error: 'path' parameter is required for file_read"
                return file_read(arguments["path"], arguments.get("offset", 0), arguments.get("limit"))
            case "file_write":
                if "path" not in arguments:
                    return "Error: 'path' parameter is required for file_write"
                if "content" not in arguments:
                    return "Error: 'content' parameter is required for file_write"
                return file_write(arguments["path"], arguments["content"])
            case "file_edit":
                if "path" not in arguments:
                    return "Error: 'path' parameter is required for file_edit"
                return file_edit(arguments["path"], arguments["old_string"], arguments["new_string"])
            case "file_delete":
                if "path" not in arguments:
                    return "Error: 'path' parameter is required for file_delete"
                return file_delete(arguments["path"], arguments.get("recursive", False))
            case "glob_search":
                if "pattern" not in arguments:
                    return "Error: 'pattern' parameter is required for glob_search"
                return glob_search(arguments["pattern"], arguments.get("path"))
            case "grep_search":
                if "pattern" not in arguments:
                    return "Error: 'pattern' parameter is required for grep_search"
                return grep_search(arguments["pattern"], arguments.get("path"), arguments.get("include"), arguments.get("ignore_case", False))
            case "list_directory":
                return list_directory(arguments.get("path"), arguments.get("recursive", False))
            case "shell_execute":
                if "command" not in arguments:
                    return "Error: 'command' parameter is required for shell_execute"
                return await shell_execute(arguments["command"], arguments.get("timeout", 120), arguments.get("cwd"))
            case "run_tests":
                return await run_tests(arguments.get("test_path"), arguments.get("framework", "auto"), arguments.get("verbose", False))
            case "test_standalone_code":
                if "code" not in arguments:
                    return "Error: 'code' parameter is required for test_standalone_code"
                result = await test_code_in_sandbox(
                    arguments["code"],
                    arguments.get("requirements", ""),
                    max_retries=2
                )
                return json.dumps(result, indent=2)
            case _:
                return f"Error: Unknown tool '{name}'"
    except KeyError as e:
        return f"Error: Missing required parameter: {e}"
    except Exception as e:
        return f"Error executing tool '{name}': {str(e)}"
