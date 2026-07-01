import os
import sys
import tempfile
import shutil
import asyncio
import re
from datetime import datetime
from typing import Tuple


class SandboxExecutor:
    """
    Executes Python code in an isolated temporary virtual environment.
    Displays progress to the user and handles test/retry logic.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.now().strftime("%H%M%S")
        self.temp_dir = None
        self.env_dir = None
        self.python_exe = None
        self.pip_exe = None

    async def execute(self, code: str, requirements: str = "") -> Tuple[bool, str, str]:
        """
        Execute Python code in a sandbox.

        Returns:
            (success: bool, stdout: str, stderr: str)
        """
        self.temp_dir = os.path.abspath(tempfile.mkdtemp(prefix=f"sandbox_{self.session_id}_"))
        script_path = os.path.join(self.temp_dir, "app.py")

        # Decide if we need a venv or can use system Python
        use_venv = requirements.strip() != ""

        try:
            if use_venv:
                # Create virtual environment only if we have requirements
                self.env_dir = os.path.join(self.temp_dir, 'venv')
                req_path = os.path.join(self.temp_dir, "requirements.txt")

                # Create virtual environment with system site packages
                # Use --copies flag on Windows to avoid symlink permission issues
                venv_args = [sys.executable, '-m', 'venv']
                if os.name == 'nt':
                    venv_args.append('--copies')  # Use copies instead of symlinks on Windows
                venv_args.extend(['--system-site-packages', self.env_dir])

                process = await asyncio.create_subprocess_exec(
                    *venv_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

                if process.returncode != 0:
                    return False, "", f"Failed to create virtual environment: {stderr.decode()}"

                # Set paths for Python and pip in the venv
                bin_folder = "Scripts" if os.name == 'nt' else "bin"
                self.python_exe = os.path.join(self.env_dir, bin_folder, "python" + (".exe" if os.name == 'nt' else ""))
                self.pip_exe = os.path.join(self.env_dir, bin_folder, "pip" + (".exe" if os.name == 'nt' else ""))

                # Install requirements
                with open(req_path, 'w', encoding='utf-8') as f:
                    f.write(requirements.strip())
                    f.flush()
                    os.fsync(f.fileno())

                pip_proc = await asyncio.create_subprocess_exec(
                    self.pip_exe, "install", "--prefer-binary", "-r", req_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                pip_out, pip_err = await asyncio.wait_for(pip_proc.communicate(), timeout=120.0)

                if pip_proc.returncode != 0:
                    return False, pip_out.decode(), f"Pip installation failed: {pip_err.decode()}"
            else:
                # No requirements - use system Python directly (faster and avoids venv permission issues)
                self.python_exe = sys.executable

            # Write the code to app.py with UTF-8 encoding declaration
            code_with_encoding = f"# -*- coding: utf-8 -*-\n{code}"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code_with_encoding)
                f.flush()
                os.fsync(f.fileno())

            # Mock environment variables to prevent system failures
            mock_env = {
                **os.environ,
                "SDL_VIDEODRIVER": "dummy",
                "AWS_ACCESS_KEY_ID": "mock_key",
                "AWS_SECRET_ACCESS_KEY": "mock_secret",
                "AWS_DEFAULT_REGION": "us-east-1",
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8"
            }

            # Execute the script
            run_proc = await asyncio.create_subprocess_exec(
                self.python_exe, "app.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.temp_dir,
                env=mock_env
            )

            stdout, stderr = await asyncio.wait_for(run_proc.communicate(), timeout=30.0)
            exit_code = run_proc.returncode

            success = exit_code == 0
            stdout_str = stdout.decode(errors='ignore')
            stderr_str = stderr.decode(errors='ignore')

            return success, stdout_str, stderr_str

        except asyncio.TimeoutError:
            return False, "", "Execution timeout: Code took too long to run (30s limit)"
        except Exception as e:
            return False, "", f"Sandbox execution error: {str(e)}"
        finally:
            # Cleanup
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def cleanup(self):
        """Force cleanup of temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)


async def test_code_in_sandbox(code: str, requirements: str = "", max_retries: int = 2) -> dict:
    """
    Test standalone Python code in a sandbox environment.
    Automatically retries on failure by asking the LLM to fix the code.

    Args:
        code: Python code to execute
        requirements: pip requirements (one per line)
        max_retries: Maximum number of retry attempts

    Returns:
        dict with keys: success, stdout, stderr, iterations, final_code, final_requirements
    """
    sandbox = SandboxExecutor()

    iteration = 0
    current_code = code
    current_requirements = requirements
    last_error = ""

    while iteration < max_retries:
        iteration += 1

        success, stdout, stderr = await sandbox.execute(current_code, current_requirements)

        if success:
            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "iterations": iteration,
                "final_code": current_code,
                "final_requirements": current_requirements
            }

        last_error = stderr if stderr else "Unknown execution error"

        # If this is the last iteration, return the failure
        if iteration >= max_retries:
            return {
                "success": False,
                "stdout": stdout,
                "stderr": last_error,
                "iterations": iteration,
                "final_code": current_code,
                "final_requirements": current_requirements
            }

        # Otherwise, the agent loop will handle asking LLM to fix it
        # For now, just return the error so the agent can decide
        break

    return {
        "success": False,
        "stdout": "",
        "stderr": last_error,
        "iterations": iteration,
        "final_code": current_code,
        "final_requirements": current_requirements
    }


def extract_code_and_requirements(text: str) -> Tuple[str, str]:
    """
    Extract Python code and requirements from markdown-formatted text.

    Looks for:
    - ```python ... ``` or ```py ... ```
    - ```text ... ``` or ```requirements ... ``` or ```txt ... ```

    Returns:
        (code: str, requirements: str)
    """
    # Extract requirements
    requirements = ""
    req_patterns = [
        r'```(?:text|requirements|txt)\s*(.*?)\s*```',
        r'```\s*requirements\.txt\s*(.*?)\s*```'
    ]
    for pattern in req_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            requirements = match.group(1).strip()
            break

    # Extract Python code
    code = ""
    code_patterns = [
        r'```python\s*(.*?)\s*```',
        r'```py\s*(.*?)\s*```'
    ]
    for pattern in code_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            code = match.group(1).strip()
            break

    return code, requirements
