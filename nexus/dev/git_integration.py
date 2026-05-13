"""
NEXUS Git Integration — Repository management via GitNexus-inspired tools.

Provides git operations:
  - Repository status, diff, log
  - Branch management
  - Commit, push, pull
  - File history
  - Blame analysis
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class GitIntegration:
    """
    Git integration for NEXUS.

    Wraps git CLI commands for repository management.

    Usage:
        git = GitIntegration(repo_path="/path/to/repo")
        status = await git.status()
        await git.commit("Fix: resolve memory leak", files=["src/main.py"])
        log = await git.log(max_entries=10)
    """

    def __init__(self, repo_path: Optional[str] = None):
        self.settings = get_settings()
        self.repo_path = repo_path or os.getcwd()

    async def _run_git(self, *args: str, cwd: Optional[str] = None) -> tuple[str, str, int]:
        """Run a git command and return (stdout, stderr, exit_code)."""
        cmd = ["git"] + list(args)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or self.repo_path,
            )
            stdout, stderr = await proc.communicate()
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0,
            )
        except FileNotFoundError:
            return "", "git not found in PATH", 1

    async def status(self) -> dict[str, Any]:
        """Get repository status."""
        stdout, stderr, code = await self._run_git("status", "--porcelain=v2")
        if code != 0:
            return {"error": stderr, "repo_path": self.repo_path}

        changed = []
        untracked = []
        staged = []

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            if line.startswith("1 "):
                # Changed entry
                parts = line.split()
                xy = parts[1] if len(parts) > 1 else ""
                path = parts[-1] if parts else ""
                if xy[0] != "." and xy[0] != "?":
                    staged.append(path)
                if xy[1] != "." and xy[1] != "?":
                    changed.append(path)
            elif line.startswith("? "):
                untracked.append(line[2:].strip())

        return {
            "repo_path": self.repo_path,
            "staged": staged,
            "changed": changed,
            "untracked": untracked,
        }

    async def log(self, max_entries: int = 20, format_str: Optional[str] = None) -> list[dict[str, str]]:
        """Get commit log."""
        fmt = format_str or "%H|%an|%ae|%ai|%s"
        stdout, stderr, code = await self._run_git(
            "log", f"--max-count={max_entries}", f"--format={fmt}"
        )
        if code != 0:
            return []

        entries = []
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) >= 5:
                entries.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })
        return entries

    async def diff(self, file_path: Optional[str] = None, staged: bool = False) -> str:
        """Get diff output."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.append(file_path)
        stdout, _, _ = await self._run_git(*args)
        return stdout

    async def commit(self, message: str, files: Optional[list[str]] = None, add_all: bool = False) -> dict[str, Any]:
        """Create a commit."""
        if add_all:
            await self._run_git("add", "-A")
        elif files:
            for f in files:
                await self._run_git("add", f)

        stdout, stderr, code = await self._run_git("commit", "-m", message)
        if code != 0:
            return {"success": False, "error": stderr}

        return {"success": True, "output": stdout.strip()}

    async def branch(self, name: Optional[str] = None, create: bool = False, delete: bool = False) -> dict[str, Any]:
        """List, create, or delete branches."""
        if name and create:
            _, stderr, code = await self._run_git("checkout", "-b", name)
            return {"success": code == 0, "error": stderr if code != 0 else ""}
        elif name and delete:
            _, stderr, code = await self._run_git("branch", "-d", name)
            return {"success": code == 0, "error": stderr if code != 0 else ""}
        else:
            stdout, _, _ = await self._run_git("branch", "-a")
            branches = [
                line.strip().lstrip("* ")
                for line in stdout.strip().split("\n")
                if line.strip()
            ]
            return {"branches": branches}

    async def push(self, remote: str = "origin", branch: str = "HEAD") -> dict[str, Any]:
        """Push to remote."""
        _, stderr, code = await self._run_git("push", remote, branch)
        return {"success": code == 0, "error": stderr if code != 0 else ""}

    async def pull(self, remote: str = "origin", branch: Optional[str] = None) -> dict[str, Any]:
        """Pull from remote."""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        stdout, stderr, code = await self._run_git(*args)
        return {"success": code == 0, "output": stdout, "error": stderr if code != 0 else ""}

    async def blame(self, file_path: str) -> list[dict[str, str]]:
        """Get blame information for a file."""
        stdout, _, code = await self._run_git("blame", "--porcelain", file_path)
        if code != 0:
            return []

        entries = []
        current = {}
        for line in stdout.split("\n"):
            if line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("author-mail "):
                current["email"] = line[12:]
            elif line.startswith("author-time "):
                current["time"] = line[12:]
            elif line.startswith("\t"):
                current["line"] = line[1:]
                entries.append(dict(current))
                current = {}
        return entries
