TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read the contents of a file. Returns the file content with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or workspace-relative path to the file"},
                    "offset": {"type": "integer", "description": "Line number to start reading from (0-indexed)"},
                    "limit": {"type": "integer", "description": "Maximum number of lines to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or workspace-relative path to the file"},
                    "content": {"type": "string", "description": "The content to write to the file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_edit",
            "description": "Edit a file by replacing a specific string with a new string. The old_string must match exactly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "old_string": {"type": "string", "description": "The exact string to find and replace"},
                    "new_string": {"type": "string", "description": "The replacement string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_delete",
            "description": "Delete a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"},
                    "recursive": {"type": "boolean", "description": "Recursively delete directories. Default false."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "Find files matching a glob pattern in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py')"},
                    "path": {"type": "string", "description": "Directory to search in. Defaults to workspace root."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search file contents using a regex pattern. Returns matching lines with file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory or file to search in"},
                    "include": {"type": "string", "description": "Glob pattern to filter files (e.g., '*.py')"},
                    "ignore_case": {"type": "boolean", "description": "Case insensitive search. Default false."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_execute",
            "description": "Execute a shell command in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds. Default 120."},
                    "cwd": {"type": "string", "description": "Working directory. Defaults to workspace root."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project's test suite or specific tests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Specific test file or directory. Empty runs all."},
                    "framework": {"type": "string", "enum": ["pytest", "jest", "mocha", "go", "cargo", "auto"], "description": "Test framework. Default 'auto'."},
                    "verbose": {"type": "boolean", "description": "Verbose output. Default false."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path. Defaults to workspace root."},
                    "recursive": {"type": "boolean", "description": "List recursively (max depth 3). Default false."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "test_standalone_code",
            "description": "REQUIRED tool for testing any NEW standalone Python code. Use this when the user asks to 'create a script', 'write a program', 'generate code', or requests any new standalone code (like fibonacci, calculators, API scripts, data processors, etc.). The code is automatically tested in an isolated sandbox environment with auto-retry on failure. User sees real-time testing progress. DO NOT just return code as text - always test it with this tool first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The complete, executable Python code including all imports and a main section that runs/demonstrates the code"},
                    "requirements": {"type": "string", "description": "Pip requirements, one per line (e.g., 'requests\\nflask\\nboto3'). Leave empty if no external dependencies needed."},
                    "description": {"type": "string", "description": "Brief description of what this code does (e.g., 'Fibonacci calculator', 'GitHub API fetcher')"},
                },
                "required": ["code"],
            },
        },
    },
]
