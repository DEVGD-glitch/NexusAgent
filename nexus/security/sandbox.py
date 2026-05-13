"""
NEXUS Sandbox — Sandboxed code execution environments.

Provides isolated execution environments for running untrusted code:
  - Local subprocess sandbox with resource limits
  - Docker container sandbox (when available)
  - Network isolation
  - Filesystem restrictions
  - Memory and CPU limits

Windows-compatible: no `resource` module, uses `python` not `python3`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import SandboxError

logger = logging.getLogger(__name__)

# Whitelist of safe shell commands for execute_shell()
SAFE_SHELL_COMMANDS = frozenset({
    "echo", "pwd", "whoami", "date", "ls", "cat", "head", "tail",
    "grep", "find", "wc", "git", "node", "python", "python3",
})


def _validate_shell_command(command: str) -> str | None:
    """Validate shell command against whitelist. Returns None if safe, error message if unsafe."""
    import shlex
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return "Invalid shell syntax"

    if not parts:
        return "Empty command"

    base_cmd = parts[0]

    # Check for dangerous operators
    dangerous = ["&&", "||", ";", ">", "<", "|", "$(", "`", ">>", "<<"]
    for op in dangerous:
        if op in command:
            return f"Dangerous operator '{op}' not allowed"

    # Check base command is in whitelist
    if base_cmd not in SAFE_SHELL_COMMANDS:
        return f"Command '{base_cmd}' not in allowed whitelist"

    return None

# Detect if `resource` module is available (Unix only)
_HAS_RESOURCE = False
try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    pass  # Windows — resource module not available

# Python executable — `python` on Windows, `python3` on Unix
_PYTHON_EXE = "python" if platform.system() == "Windows" else "python3"


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


class LocalSandbox:
    """
    Local subprocess sandbox with resource limits.

    Executes code in a subprocess with:
      - Time limits (timeout)
      - Memory limits (via resource module on Unix only)
      - Filesystem restrictions (working directory isolation)
      - Network restrictions (optional: unshare on Linux)
      - Output size limits

    Windows-compatible: resource limits are skipped on Windows.
    For production, use DockerSandbox instead.
    """

    # Maximum output size (5MB)
    MAX_OUTPUT_BYTES = 5 * 1024 * 1024

    # Dangerous patterns that should never be executed
    BLOCKED_PATTERNS = [
        "rm -rf /",
        "mkfs.",
        "dd if=",
        ":(){ :|:& };:",
        "fork bomb",
        # Python-specific dangerous patterns
        "__import__(",
        "__import__('",
        "importlib.import_module",
        "ctypes",
        "winreg",
        "import os; os.system",
        "import os; os.popen",
        "subprocess.run([\"rm\"",
        "os.chmod(0o777",
        "import pwd",
        "import spwd",
        "import crypt",
        "multiprocessing",
        "concurrent.futures",
        # Key exfiltration patterns
        ".send_keys(",
    ]

    # Additional regex-based checks (evaluated separately)
    _DANGEROUS_IMPORTS = [
        "os", "sys", "subprocess", "socket", "requests", "urllib",
        "http", "ftplib", "telnetlib", "pty", "termios", "tty",
        "resource", "signal", "multiprocessing", "concurrent",
        "ctypes", "winreg", "winsound", "msvcrt",
        "importlib",
    ]

    def __init__(
        self,
        timeout: int = 30,
        max_memory_mb: int = 512,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        working_dir: Optional[str] = None,
        allowed_paths: Optional[list[str]] = None,
    ):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.max_output_bytes = max_output_bytes
        self.working_dir = working_dir or tempfile.gettempdir()
        self.allowed_paths = allowed_paths or []

    def _check_for_dangerous_code(self, code: str) -> Optional[str]:
        """Check if code contains dangerous patterns."""
        import re
        code_lower = code.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in code_lower:
                return f"Code contains dangerous pattern: {pattern}"

        # Additional check: imports of dangerous modules
        for dangerous in self._DANGEROUS_IMPORTS:
            # Match import statements (import x, from x import, __import__("x"))
            if re.search(rf'(?:from|import)\s+{re.escape(dangerous)}', code, re.IGNORECASE):
                return f"Code imports dangerous module: {dangerous}"

        return None

    def _build_sandbox_preamble(self, effective_timeout: int) -> str:
        """Build the sandbox preamble for the subprocess.

        On Unix, includes resource.setrlimit() calls.
        On Windows, only sets up basic isolation (no resource limits available).
        """
        if _HAS_RESOURCE:
            return (
                "import resource, os, sys\n"
                "try:\n"
                f"    resource.setrlimit(resource.RLIMIT_AS, ({self.max_memory_mb * 1024 * 1024}, {self.max_memory_mb * 1024 * 1024}))\n"
                "except (ValueError, OSError, AttributeError):\n"
                "    pass\n"
                "try:\n"
                f"    resource.setrlimit(resource.RLIMIT_CPU, ({effective_timeout + 5}, {effective_timeout + 5}))\n"
                "except (ValueError, OSError, AttributeError):\n"
                "    pass\n"
                "try:\n"
                "    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n"
                "except (ValueError, OSError, AttributeError):\n"
                "    pass\n"
                "# End of sandbox preamble\n\n"
            )
        else:
            # Windows: no resource module — rely on timeout only
            return (
                "import os, sys\n"
                "# Windows sandbox: resource limits not available\n"
                "# Relying on timeout for safety\n"
                "# End of sandbox preamble\n\n"
            )

    async def execute_python(
        self,
        code: str,
        timeout: Optional[int] = None,
        env_vars: Optional[dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute Python code in a sandboxed subprocess.

        Args:
            code: Python code to execute.
            timeout: Execution timeout in seconds.
            env_vars: Additional environment variables.

        Returns:
            SandboxResult with execution output and metadata.

        Raises:
            SandboxError: If code contains dangerous patterns or execution fails.
        """
        # Security check
        danger = self._check_for_dangerous_code(code)
        if danger:
            raise SandboxError(reason=danger)

        effective_timeout = timeout or self.timeout
        start_time = time.monotonic()

        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=self.working_dir
        ) as f:
            preamble = self._build_sandbox_preamble(effective_timeout)
            f.write(preamble + code)
            temp_path = f.name

        # Prepare environment — strip sensitive keys
        env = os.environ.copy()
        for key in [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ZAI_API_KEY",
            "GOOGLE_API_KEY", "NEXUS_SECRET_KEY",
            "SERPAPI_KEY", "BRAVE_SEARCH_KEY", "TELEGRAM_BOT_TOKEN",
            "LANGFUSE_SECRET_KEY",
        ]:
            env.pop(key, None)
        if env_vars:
            env.update(env_vars)

        # Use correct Python executable for the platform
        python_exe = _PYTHON_EXE

        try:
            # On Windows, use CREATE_NO_WINDOW to avoid console flash
            kwargs = {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "cwd": self.working_dir,
                "env": env,
            }
            if platform.system() == "Windows":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

            proc = await asyncio.create_subprocess_exec(
                python_exe, temp_path,
                **kwargs,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                if platform.system() == "Windows":
                    try:
                        taskkill_proc = await asyncio.create_subprocess_exec(
                            "taskkill", "/T", "/F", "/PID", str(proc.pid),
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await taskkill_proc.wait()
                    except Exception:
                        logger.warning("Failed to kill child processes for PID %s", proc.pid)
                await proc.wait()
                stdout_bytes, stderr_bytes = b"", b"Execution timed out"
                timed_out = True

            # Truncate output if too large
            stdout = stdout_bytes.decode("utf-8", errors="replace")[:self.max_output_bytes]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:self.max_output_bytes]

            execution_time = (time.monotonic() - start_time) * 1000

            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode if not timed_out else -1,
                timed_out=timed_out,
                execution_time_ms=execution_time,
            )

        except Exception as exc:
            raise SandboxError(reason=str(exc), command=code[:100])
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def execute_shell(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """
        Execute a shell command in a sandboxed environment.

        Only allows safe commands. Dangerous commands are blocked.
        """
        danger = self._check_for_dangerous_code(command)
        if danger:
            raise SandboxError(reason=danger, command=command)

        # Validate against whitelist
        error = _validate_shell_command(command)
        if error:
            raise SandboxError(reason=error, command=command)

        effective_timeout = timeout or self.timeout
        start_time = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_bytes, stderr_bytes = b"", b"Execution timed out"
                timed_out = True

            stdout = stdout_bytes.decode("utf-8", errors="replace")[:self.max_output_bytes]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:self.max_output_bytes]

            execution_time = (time.monotonic() - start_time) * 1000

            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode if not timed_out else -1,
                timed_out=timed_out,
                execution_time_ms=execution_time,
            )

        except Exception as exc:
            raise SandboxError(reason=str(exc), command=command[:100])


class DockerSandbox:
    """
    Docker container sandbox for production code execution.

    Provides full isolation with:
      - Separate filesystem
      - Network isolation (no network by default)
      - Memory and CPU limits
      - Read-only root filesystem
      - Non-root user execution

    Requires Docker to be installed and the sandbox image to be built.
    """

    def __init__(
        self,
        image: Optional[str] = None,
        timeout: int = 30,
        max_memory_mb: int = 512,
        cpu_quota: int = 50000,  # 50% of one CPU
    ):
        settings = get_settings()
        self.image = image or settings.sandbox_docker_image
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.cpu_quota = cpu_quota

    async def execute_python(
        self,
        code: str,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """Execute Python code in a Docker container."""
        effective_timeout = timeout or self.timeout
        start_time = time.monotonic()

        # Write code to temp file that will be mounted
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            cmd = [
                "docker", "run",
                "--rm",
                "--network", "none",
                "--memory", f"{self.max_memory_mb}m",
                "--cpus", f"{self.cpu_quota / 100000:.1f}",
                "--read-only",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true",
                "--security-opt", "seccomp=default",
                "--user", "1000:1000",
                "--tmpfs", "/tmp:size=100m",
                "-v", f"{temp_path}:/sandbox/code.py:ro",
                self.image,
                "python3", "/sandbox/code.py",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout + 10,  # Extra buffer for Docker overhead
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_bytes, stderr_bytes = b"", b"Execution timed out"
                timed_out = True

            execution_time = (time.monotonic() - start_time) * 1000

            return SandboxResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode if not timed_out else -1,
                timed_out=timed_out,
                execution_time_ms=execution_time,
            )

        except FileNotFoundError:
            raise SandboxError(
                reason="Docker is not installed or not in PATH. Use LocalSandbox instead.",
            )
        except Exception as exc:
            raise SandboxError(reason=str(exc))
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def is_available(self) -> bool:
        """Check if Docker is available and the sandbox image exists."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "images", "-q", self.image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return bool(stdout.strip())
        except FileNotFoundError:
            return False


def get_sandbox() -> LocalSandbox | DockerSandbox:
    """Get the appropriate sandbox based on configuration."""
    settings = get_settings()
    if settings.sandbox_enabled:
        # Try Docker first, fall back to local
        try:
            return DockerSandbox(image=settings.sandbox_docker_image)
        except Exception:
            pass
    return LocalSandbox()
