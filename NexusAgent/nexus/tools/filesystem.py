"""NEXUS — Secure Filesystem Operations."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# Allowed root directories
ALLOWED_ROOTS = [
    Path.cwd().resolve(),
    (Path.home() / "nexus-workspace").resolve(),
    (Path.home() / "Desktop").resolve(),
    (Path.home() / "Documents").resolve(),
    (Path.home() / "Downloads").resolve(),
]

# Max file size for reading (10MB)
MAX_READ_SIZE = 10 * 1024 * 1024

# Blocked extensions
BLOCKED_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".sh"}


def validate_path(path: str) -> tuple[Path | None, str]:
    """Validate path is within allowed roots."""
    try:
        resolved = Path(path).resolve()

        # Check for path traversal
        for root in ALLOWED_ROOTS:
            if resolved.is_relative_to(root):
                return resolved, ""

        return None, f"Path '{path}' is outside allowed directories"
    except Exception as e:
        return None, str(e)


def read_file(path: str, max_lines: int = 1000) -> dict:
    """Read a file with path traversal protection."""
    safe_path, error = validate_path(path)
    if error:
        return {"success": False, "error": error}

    if not safe_path.exists():
        return {"success": False, "error": f"File not found: {path}"}

    if safe_path.is_dir():
        return {"success": False, "error": f"Path is a directory: {path}"}

    if safe_path.suffix.lower() in BLOCKED_EXTENSIONS:
        return {"success": False, "error": f"File type '{safe_path.suffix}' is not allowed"}

    try:
        # Check file size
        size = safe_path.stat().st_size
        if size > MAX_READ_SIZE:
            return {"success": False, "error": f"File too large ({size / 1024 / 1024:.1f}MB, max 10MB)"}

        content = safe_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        return {
            "success": True,
            "content": "\n".join(lines[:max_lines]),
            "total_lines": len(lines),
            "truncated": len(lines) > max_lines,
            "size": size,
            "path": str(safe_path),
        }
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str, content: str) -> dict:
    """Write to a file with path traversal protection."""
    safe_path, error = validate_path(path)
    if error:
        return {"success": False, "error": error}

    if safe_path.suffix.lower() in BLOCKED_EXTENSIONS:
        return {"success": False, "error": f"File type '{safe_path.suffix}' is not allowed"}

    try:
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(safe_path), "size": len(content)}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_directory(path: str = ".") -> dict:
    """List directory contents with path traversal protection."""
    safe_path, error = validate_path(path)
    if error:
        return {"success": False, "error": error}

    if not safe_path.exists():
        return {"success": False, "error": f"Path not found: {path}"}

    if not safe_path.is_dir():
        return {"success": False, "error": f"Path is not a directory: {path}"}

    try:
        entries = []
        for entry in safe_path.iterdir():
            stat = entry.stat()
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else 0,
                "modified": stat.st_mtime,
            })
        entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
        return {"success": True, "entries": entries, "count": len(entries), "path": str(safe_path)}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_files(path: str, pattern: str = "*") -> dict:
    """Search for files matching a pattern."""
    safe_path, error = validate_path(path)
    if error:
        return {"success": False, "error": error}

    try:
        matches = list(safe_path.rglob(pattern))
        results = []
        for m in matches[:100]:  # Limit results
            if m.is_file():
                results.append({
                    "path": str(m.relative_to(safe_path)),
                    "size": m.stat().st_size,
                })
        return {"success": True, "files": results, "count": len(results), "truncated": len(matches) > 100}
    except Exception as e:
        return {"success": False, "error": str(e)}
