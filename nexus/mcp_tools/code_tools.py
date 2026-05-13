"""
NEXUS MCP Code Execution Tools.
"""

import json
import sys
from typing import Any, Optional


async def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
) -> str:
    """Execute code in a sandboxed environment."""
    try:
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=timeout)
        result = await sandbox.execute_python(code, timeout=timeout)
        return json.dumps({
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "execution_time_ms": result.execution_time_ms,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def execute_sandboxed(
    command: str,
    timeout: int = 30,
    allowed_dirs: Optional[list[str]] = None,
) -> str:
    """Execute a shell command in a sandboxed environment."""
    try:
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=timeout)
        result = await sandbox.execute_shell(command, timeout=timeout)
        return json.dumps({
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def install_package(
    package: str,
    version: Optional[str] = None,
) -> str:
    """Install a Python package."""
    try:
        import asyncio

        pkg_spec = f"{package}=={version}" if version else package
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", pkg_spec,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            return json.dumps({
                "status": "success" if proc.returncode == 0 else "failed",
                "package": package,
                "version": version,
                "output": (stdout or b"").decode(errors="replace"),
                "error": (stderr or b"").decode(errors="replace"),
            })
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return json.dumps({"status": "failed", "package": package, "error": "Timeout (120s)"})
    except Exception as e:
        return json.dumps({"error": str(e)})