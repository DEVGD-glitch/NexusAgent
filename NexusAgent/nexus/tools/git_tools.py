"""NEXUS — Git Integration Tools."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def _run_git(args: list[str], cwd: str = ".") -> dict:
    """Run a git command and return result."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_status(cwd: str = ".") -> dict:
    """Get git status of a repository."""
    result = _run_git(["status", "--porcelain"], cwd=cwd)
    if result["success"]:
        lines = result["stdout"].split("\n") if result["stdout"] else []
        return {
            "clean": len(lines) == 0,
            "modified": len([l for l in lines if l.startswith(" M") or l.startswith("M ")]),
            "untracked": len([l for l in lines if l.startswith("??")]),
            "staged": len([l for l in lines if l.startswith("M ") or l.startswith("A ")]),
            "details": result["stdout"],
        }
    return result


def git_diff(cwd: str = ".", staged: bool = False) -> dict:
    """Get git diff."""
    args = ["diff", "--stat"]
    if staged:
        args.insert(1, "--cached")
    return _run_git(args, cwd=cwd)


def git_log(cwd: str = ".", limit: int = 10) -> dict:
    """Get recent git commits."""
    fmt = "--pretty=format:%h|%an|%ad|%s"
    return _run_git(["log", f"-{limit}", fmt, "--date=short"], cwd=cwd)


def git_commit(message: str, cwd: str = ".") -> dict:
    """Stage all changes and commit."""
    _run_git(["add", "-A"], cwd=cwd)
    return _run_git(["commit", "-m", message], cwd=cwd)


def git_branch(cwd: str = ".") -> dict:
    """List branches and current branch."""
    result = _run_git(["branch", "--show-current"], cwd=cwd)
    current = result.get("stdout", "") if result["success"] else ""
    branches = _run_git(["branch"], cwd=cwd)
    branch_list = [b.strip().lstrip("* ") for b in branches.get("stdout", "").split("\n") if b.strip()]
    return {"current": current, "branches": branch_list}


def git_checkout(branch: str, cwd: str = ".") -> dict:
    """Switch to a branch."""
    return _run_git(["checkout", branch], cwd=cwd)


def git_create_branch(branch: str, cwd: str = ".") -> dict:
    """Create and switch to a new branch."""
    _run_git(["checkout", "-b", branch], cwd=cwd)
    return {"success": True, "branch": branch}
