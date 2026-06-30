import json
from app.tools.filesystem import (
    file_read, file_write, file_edit, file_delete,
    glob_search, grep_search, list_directory,
)
from app.tools.shell import shell_execute, run_tests


async def dispatch_tool(name: str, arguments: dict) -> str:
    match name:
        case "file_read":
            return file_read(arguments["path"], arguments.get("offset", 0), arguments.get("limit"))
        case "file_write":
            return file_write(arguments["path"], arguments["content"])
        case "file_edit":
            return file_edit(arguments["path"], arguments["old_string"], arguments["new_string"])
        case "file_delete":
            return file_delete(arguments["path"], arguments.get("recursive", False))
        case "glob_search":
            return glob_search(arguments["pattern"], arguments.get("path"))
        case "grep_search":
            return grep_search(arguments["pattern"], arguments.get("path"), arguments.get("include"), arguments.get("ignore_case", False))
        case "list_directory":
            return list_directory(arguments.get("path"), arguments.get("recursive", False))
        case "shell_execute":
            return await shell_execute(arguments["command"], arguments.get("timeout", 120), arguments.get("cwd"))
        case "run_tests":
            return await run_tests(arguments.get("test_path"), arguments.get("framework", "auto"), arguments.get("verbose", False))
        case _:
            return f"Error: Unknown tool '{name}'"
