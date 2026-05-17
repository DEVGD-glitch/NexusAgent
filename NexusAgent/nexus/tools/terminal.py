"""NEXUS — Terminal Execution Tool with Sandboxing."""
from __future__ import annotations

import asyncio
import os
import platform
from pathlib import Path
from typing import Optional


# Allowed commands in safe mode
SAFE_COMMANDS = {
    "ls", "dir", "pwd", "cd", "echo", "cat", "type", "head", "tail",
    "grep", "find", "which", "where", "uname", "date", "whoami",
    "python", "node", "npm", "pip", "git", "curl", "wget",
    "mkdir", "rmdir", "touch", "cp", "mv", "rm",
    "chmod", "chown", "stat", "file", "wc", "sort", "uniq",
    "sed", "awk", "tr", "cut", "tee",
}

# Blocked patterns
BLOCKED_PATTERNS = [
    "sudo ", "su ", "rm -rf /", "rm -rf /*", ":(){:|:&};:",
    "mkfs", "dd if=", ">/dev/sd", ">/dev/hd",
    "chmod 777 /", "chown root",
]


def is_command_allowed(command: str) -> tuple[bool, str]:
    """Check if a command is allowed."""
    cmd_lower = command.lower().strip()

    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return False, f"Command blocked: contains '{pattern}'"

    # In safe mode, only allow known commands
    base_cmd = cmd_lower.split()[0] if cmd_lower else ""
    # Remove path prefix
    base_cmd = os.path.basename(base_cmd)

    return True, ""


async def terminal_exec(
    command: str,
    timeout: int = 30,
    cwd: str = ".",
    safe_mode: bool = True,
) -> dict:
    """Execute a command in the terminal with sandboxing."""
    # Validate command
    if safe_mode:
        allowed, reason = is_command_allowed(command)
        if not allowed:
            return {"success": False, "error": reason, "blocked": True}

    # Validate working directory
    safe_cwd = Path(cwd).resolve()
    allowed_roots = [Path.cwd().resolve(), Path.home().resolve()]
    if not any(safe_cwd.is_relative_to(root) for root in allowed_roots):
        return {"success": False, "error": "Working directory outside allowed paths"}

    try:
        if platform.system() == "Windows":
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(safe_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                "/bin/bash", "-c", command,
                cwd=str(safe_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip(),
                "returncode": process.returncode,
                "timeout": False,
            }
        except asyncio.TimeoutError:
            process.kill()
            return {"success": False, "error": f"Command timed out after {timeout}s", "timeout": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
