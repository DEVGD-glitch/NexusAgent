"""
NEXUS MCP File Operations Tools.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional


async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's contents."""
    try:
        from nexus.security.permissions import check_permission, PermissionAction

        check_permission(PermissionAction.READ, path)
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
        return json.dumps({"path": path, "content": content, "size": len(content)})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
) -> str:
    """Write content to a file."""
    try:
        from nexus.security.permissions import check_permission, PermissionAction

        check_permission(PermissionAction.WRITE, path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return json.dumps({"status": "written", "path": path, "size": len(content)})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_files(
    directory: str = ".",
    pattern: str = "*",
) -> str:
    """List files in a directory matching a pattern."""
    try:
        from pathlib import Path

        files = list(Path(directory).glob(pattern))
        return json.dumps({
            "directory": directory,
            "pattern": pattern,
            "files": [str(f) for f in files],
            "count": len(files),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def delete_file(path: str) -> str:
    """Delete a file."""
    try:
        from nexus.security.permissions import check_permission, PermissionAction

        check_permission(PermissionAction.DELETE, path)
        os.remove(path)
        return json.dumps({"status": "deleted", "path": path})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def move_file(source: str, destination: str) -> str:
    """Move a file to a new location."""
    try:
        from nexus.security.permissions import check_permission, PermissionAction
        from pathlib import Path

        check_permission(PermissionAction.WRITE, destination)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        os.rename(source, destination)
        return json.dumps({"status": "moved", "source": source, "destination": destination})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def copy_file(source: str, destination: str) -> str:
    """Copy a file to a new location."""
    try:
        from nexus.security.permissions import check_permission, PermissionAction
        import shutil
        from pathlib import Path

        check_permission(PermissionAction.WRITE, destination)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return json.dumps({"status": "copied", "source": source, "destination": destination})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def search_files(
    query: str,
    path: str = ".",
    file_pattern: str = "*",
) -> str:
    """Search for text within files."""
    try:
        import asyncio

        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_exec(
                "findstr", "/s", "/l", query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "grep", "-r", "-l", query, "--include=" + file_pattern, path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace").strip()
        files = output.split("\n") if output else []
        return json.dumps({"query": query, "path": path, "files": files, "count": len(files)})
    except Exception as e:
        return json.dumps({"error": str(e)})