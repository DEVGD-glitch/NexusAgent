"""
NEXUS Per-Action Docker Sandbox — Isolate every risky action in a fresh container.

Each action gets its own ephemeral Docker container with:
  - No network (except browser-service for web actions)
  - Read-only filesystem (except /tmp)
  - CPU/memory limits
  - All capabilities dropped
  - No-new-privileges
  - Seccomp default profile

Wraps the existing DockerSandbox from nexus.security.sandbox and adds
per-action lifecycle management.

Usage:
    sandbox = PerActionSandbox()
    async with sandbox.isolate("code_execution") as ctx:
        result = await ctx.run("python3", ["-c", code])
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import SandboxError
from nexus.security.sandbox import SandboxResult

logger = logging.getLogger(__name__)


SANDBOX_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "alpine": "alpine:3.19",
    "browser": "nexus-browser-sandbox:latest",
}


@dataclass
class IsolationContext:
    """Context for a single isolated action."""
    container_id: str = ""
    action_type: str = ""
    start_time: float = 0.0
    temp_dir: str = ""
    network_enabled: bool = False


class PerActionSandbox:
    """
    Creates ephemeral Docker containers for each risky action.

    Every container is:
      - Fresh (no state between actions)
      - Resource-limited
      - Network-isolated (unless explicitly needed)
      - Auto-cleaned (even on crash)
    """

    def __init__(self, image: str = "python:3.11-slim"):
        self.default_image = image
        self.settings = get_settings()
        self._active_containers: set[str] = set()

    @asynccontextmanager
    async def isolate(
        self,
        action_type: str = "python",
        code: Optional[str] = None,
        files: Optional[dict[str, str]] = None,
        network: bool = False,
        timeout: int = 30,
        memory_mb: int = 256,
        cpu_quota: int = 50000,
    ) -> AsyncIterator[IsolationContext]:
        """
        Context manager for running an isolated action.

        Args:
            action_type: Type of sandbox (python, node, alpine, browser)
            code: Inline code to execute (written to /sandbox/entrypoint)
            files: Extra files to mount {path_in_container: content}
            network: Enable network access (default: isolated)
            timeout: Max execution time in seconds
            memory_mb: Max memory in MB
            cpu_quota: CPU quota (100000 = 1 core)

        Usage:
            async with sandbox.isolate("python", code="print('hi')") as ctx:
                result = await ctx.run(...)
        """
        ctx = IsolationContext(
            action_type=action_type,
            start_time=time.monotonic(),
            network_enabled=network,
        )

        docker_args = [
            "docker", "run",
            "--rm",
            "-d",  # Detached — we'll exec into it
            "--memory", f"{memory_mb}m",
            "--cpus", f"{cpu_quota / 100000:.1f}",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--security-opt", "seccomp=default",
            "--user", "1000:1000",
            "--tmpfs", "/tmp:size=100m",
            "--tmpfs", "/sandbox:size=100m,exec",
        ]

        if not network:
            docker_args.extend(["--network", "none"])

        image = SANDBOX_IMAGES.get(action_type, self.default_image)

        # Write code/files to temp directory
        temp_dir_obj = tempfile.TemporaryDirectory()
        ctx.temp_dir = temp_dir_obj.name
        temp_path = Path(temp_dir_obj.name)

        if code:
            (temp_path / "entrypoint").write_text(code)
            docker_args.extend(["-v", f"{temp_path / 'entrypoint'}:/sandbox/entrypoint:ro"])

        if files:
            for path, content in files.items():
                f_path = temp_path / path.lstrip("/")
                f_path.parent.mkdir(parents=True, exist_ok=True)
                f_path.write_text(content)
                docker_args.extend(["-v", f"{f_path}:/sandbox/{path.lstrip('/')}:ro"])

        docker_args.append(image)
        docker_args.extend(["sleep", "3600"])  # Keep alive for commands

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            container_id = stdout.decode().strip()

            if not container_id:
                raise SandboxError(f"Failed to start sandbox container: {stderr.decode()}")

            ctx.container_id = container_id
            self._active_containers.add(container_id)

            yield ctx

        finally:
            if ctx.container_id:
                await self._cleanup_container(ctx.container_id)
                self._active_containers.discard(ctx.container_id)
            try:
                temp_dir_obj.cleanup()
            except Exception:
                pass

    async def run_command(self, ctx: IsolationContext, cmd: list[str], timeout: int = 30) -> SandboxResult:
        """Run a command inside the isolation context."""
        if not ctx.container_id:
            raise SandboxError("No active isolation context")

        exec_cmd = [
            "docker", "exec",
            ctx.container_id,
        ] + cmd

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = b"", b"Command timed out"
                timed_out = True

            elapsed = (time.monotonic() - start) * 1000
            return SandboxResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode if not timed_out else -1,
                timed_out=timed_out,
                execution_time_ms=elapsed,
            )
        except FileNotFoundError:
            raise SandboxError("Docker is not installed or not in PATH")

    async def run_python(self, ctx: IsolationContext, code: str, timeout: int = 30) -> SandboxResult:
        """Run Python code inside the isolation context."""
        return await self.run_command(ctx, ["python3", "-c", code], timeout=timeout)

    async def run_shell(self, ctx: IsolationContext, command: str, timeout: int = 30) -> SandboxResult:
        """Run a shell command inside the isolation context."""
        return await self.run_command(ctx, ["sh", "-c", command], timeout=timeout)

    async def _cleanup_container(self, container_id: str) -> None:
        """Force remove a container."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", container_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

    async def cleanup_all(self) -> None:
        """Clean up all active containers."""
        for cid in list(self._active_containers):
            await self._cleanup_container(cid)
        self._active_containers.clear()

    async def is_available(self) -> bool:
        """Check if Docker is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info", "--format", "{{.ServerVersion}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            return bool(stdout.strip())
        except FileNotFoundError:
            return False
