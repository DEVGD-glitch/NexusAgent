"""
NEXUS Code Execution Backends — Multiple execution environments.

Supports:
  - Local subprocess (default)
  - Docker container (isolated)
  - HTTP-based remote execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import SandboxError

# Python executable — `python` on Windows, `python3` on Unix
_PYTHON_EXE = "python" if platform.system() == "Windows" else "python3"

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a code execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    language: str = "python"
    timed_out: bool = False
    execution_time_ms: float = 0.0
    backend: str = "local"


class CodeExecutor:
    """
    Multi-backend code executor.

    Routes code execution to the appropriate backend:
      - local: subprocess with resource limits
      - docker: Docker container isolation
      - remote: HTTP-based execution service

    Usage:
        executor = CodeExecutor()
        result = await executor.execute("print('Hello')", language="python")
    """

    LANGUAGE_EXTENSIONS = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "bash": ".sh",
        "ruby": ".rb",
        "go": ".go",
        "rust": ".rs",
    }

    LANGUAGE_COMMANDS = {
        "python": [_PYTHON_EXE, "{file}"],
        "javascript": ["node", "{file}"],
        "typescript": ["npx", "ts-node", "{file}"],
        "bash": ["bash", "{file}"],
        "ruby": ["ruby", "{file}"],
        "go": ["go", "run", "{file}"],
        "rust": ["rustc", "{file}", "-o", "{output}", "&&", "{output}"],
    }

    def __init__(self, backend: str = "auto", timeout: int = 30):
        self.settings = get_settings()
        self.backend = backend
        self.timeout = timeout

    def _select_backend(self) -> str:
        """Select the appropriate execution backend."""
        if self.backend != "auto":
            return self.backend
        if self.settings.sandbox_enabled:
            return "docker"
        return "local"

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        env_vars: Optional[dict[str, str]] = None,
        stdin: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute code in the selected backend.

        Args:
            code: Code to execute.
            language: Programming language.
            timeout: Execution timeout in seconds.
            env_vars: Additional environment variables.
            stdin: Standard input for the process.

        Returns:
            ExecutionResult with output and metadata.
        """
        effective_timeout = timeout or self.timeout
        backend = self._select_backend()

        if backend == "docker":
            return await self._execute_docker(code, language, effective_timeout)
        elif backend == "remote":
            return await self._execute_remote(code, language, effective_timeout)
        else:
            return await self._execute_local(code, language, effective_timeout, env_vars, stdin)

    async def _execute_local(
        self,
        code: str,
        language: str,
        timeout: int,
        env_vars: Optional[dict[str, str]] = None,
        stdin: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute code locally in a subprocess."""
        start = time.monotonic()
        ext = self.LANGUAGE_EXTENSIONS.get(language, ".txt")
        cmd_template = self.LANGUAGE_COMMANDS.get(language)

        if not cmd_template:
            return ExecutionResult(
                stderr=f"Unsupported language: {language}",
                exit_code=1,
                language=language,
                backend="local",
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            cmd = [c.replace("{file}", temp_path).replace("{output}", temp_path.replace(ext, ""))
                   for c in cmd_template]

            env = os.environ.copy()
            # Remove sensitive keys
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ZAI_API_KEY", "GOOGLE_API_KEY", "NEXUS_SECRET_KEY"]:
                env.pop(key, None)
            if env_vars:
                env.update(env_vars)

            # Handle compound commands (e.g., compile then run for Rust)
            if "&&" in cmd:
                split_idx = cmd.index("&&")
                compile_cmd = cmd[:split_idx]
                run_cmd = cmd[split_idx + 1:]

                # Step 1: Compile (no stdin for compiler)
                compile_proc = await asyncio.create_subprocess_exec(
                    *compile_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                try:
                    compile_stdout, compile_stderr = await asyncio.wait_for(
                        compile_proc.communicate(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    compile_proc.kill()
                    await compile_proc.wait()
                    return ExecutionResult(
                        stdout="",
                        stderr=f"Compilation timed out after {timeout}s",
                        exit_code=-1,
                        language=language,
                        timed_out=True,
                        execution_time_ms=(time.monotonic() - start) * 1000,
                        backend="local",
                    )

                if compile_proc.returncode != 0:
                    return ExecutionResult(
                        stdout=compile_stdout.decode("utf-8", errors="replace")[:50000],
                        stderr=compile_stderr.decode("utf-8", errors="replace")[:50000],
                        exit_code=compile_proc.returncode,
                        language=language,
                        execution_time_ms=(time.monotonic() - start) * 1000,
                        backend="local",
                    )

                # Step 2: Run the compiled binary
                proc = await asyncio.create_subprocess_exec(
                    *run_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE if stdin else None,
                    env=env,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE if stdin else None,
                    env=env,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode() if stdin else None),
                    timeout=timeout,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_bytes, stderr_bytes = b"", f"Execution timed out after {timeout}s".encode()
                timed_out = True

            return ExecutionResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace")[:50000],
                stderr=stderr_bytes.decode("utf-8", errors="replace")[:50000],
                exit_code=proc.returncode if not timed_out else -1,
                language=language,
                timed_out=timed_out,
                execution_time_ms=(time.monotonic() - start) * 1000,
                backend="local",
            )

        except FileNotFoundError as e:
            return ExecutionResult(
                stderr=f"Interpreter not found: {e}",
                exit_code=1,
                language=language,
                backend="local",
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def _execute_docker(
        self,
        code: str,
        language: str,
        timeout: int,
    ) -> ExecutionResult:
        """Execute code in a Docker container."""
        start = time.monotonic()
        ext = self.LANGUAGE_EXTENSIONS.get(language, ".txt")

        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            image_map = {
                "python": "python:3.12-slim",
                "javascript": "node:20-slim",
                "ruby": "ruby:3.2-slim",
                "go": "golang:1.22-alpine",
            }
            image = image_map.get(language, self.settings.sandbox_docker_image)

            cmd_map = {
                "python": ["python3", "/sandbox/code.py"],
                "javascript": ["node", "/sandbox/code.js"],
                "bash": ["bash", "/sandbox/code.sh"],
            }
            run_cmd = cmd_map.get(language, ["python3", f"/sandbox/code{ext}"])

            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "0.5",
                "-v", f"{temp_path}:/sandbox/code{ext}:ro",
                image,
            ] + run_cmd

            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout + 10,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_bytes, stderr_bytes = b"", b"Execution timed out"
                timed_out = True

            return ExecutionResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode if not timed_out else -1,
                language=language,
                timed_out=timed_out,
                execution_time_ms=(time.monotonic() - start) * 1000,
                backend="docker",
            )

        except FileNotFoundError:
            return ExecutionResult(
                stderr="Docker not available. Install Docker or use local backend.",
                exit_code=1,
                language=language,
                backend="docker",
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def _execute_remote(
        self,
        code: str,
        language: str,
        timeout: int,
    ) -> ExecutionResult:
        """Execute code via a remote HTTP execution service."""
        start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=timeout + 5) as client:
                response = await client.post(
                    f"{self.settings.browser_service_url}/execute",
                    json={"code": code, "language": language, "timeout": timeout},
                )

                if response.status_code == 200:
                    data = response.json()
                    return ExecutionResult(
                        stdout=data.get("stdout", ""),
                        stderr=data.get("stderr", ""),
                        exit_code=data.get("exit_code", 0),
                        language=language,
                        execution_time_ms=(time.monotonic() - start) * 1000,
                        backend="remote",
                    )
                else:
                    return ExecutionResult(
                        stderr=f"Remote execution failed: HTTP {response.status_code}",
                        exit_code=1,
                        language=language,
                        backend="remote",
                    )
        except Exception as e:
            return ExecutionResult(
                stderr=f"Remote execution unavailable: {e}",
                exit_code=1,
                language=language,
                backend="remote",
            )
