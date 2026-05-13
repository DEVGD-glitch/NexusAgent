"""
NEXUS Terminal — Autonomous sandboxed terminal interaction.

Provides:
  - Async command execution with timeout management
  - Command output parsing for errors and results
  - Interactive sessions with persistent state
  - Working directory management
  - Environment variable handling
  - Shell session persistence
  - Integration with the sandbox for safe execution
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import SandboxError

logger = logging.getLogger(__name__)

# Shell detection
_SHELL = "/bin/bash" if platform.system() != "Windows" else "cmd.exe"


@dataclass
class CommandResult:
    """Result of a terminal command execution."""
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    execution_time_ms: float = 0.0
    working_dir: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "execution_time_ms": self.execution_time_ms,
            "working_dir": self.working_dir,
            "success": self.success,
        }


@dataclass
class ParsedOutput:
    """Parsed command output with extracted structured data."""
    raw_stdout: str
    raw_stderr: str
    exit_code: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)

    # Common error patterns
    ERROR_PATTERNS = [
        r"(?i)error:\s*(.+)",
        r"(?i)fatal:\s*(.+)",
        r"(?i)exception:\s*(.+)",
        r"(?i)traceback \(most recent call last\)",
        r"(?i)failed:\s*(.+)",
        r"^\s*\^--\s*(.+)",
        r"(?i)cannot find (.+)",
        r"(?i)no such file(?: or directory)?:\s*(.+)",
        r"(?i)permission denied",
    ]

    WARNING_PATTERNS = [
        r"(?i)warning:\s*(.+)",
        r"(?i)warn:\s*(.+)",
        r"(?i)deprecated:\s*(.+)",
    ]

    def __post_init__(self):
        """Parse the output for structured data."""
        self._parse_errors()
        self._parse_warnings()
        self._parse_file_paths()
        self._parse_urls()
        self._parse_numbers()

    def _parse_errors(self):
        for pattern in self.ERROR_PATTERNS:
            for match in re.finditer(pattern, self.raw_stderr or self.raw_stdout):
                group = match.group(1) if match.lastindex else match.group(0)
                if group and group.strip() not in self.errors:
                    self.errors.append(group.strip())

    def _parse_warnings(self):
        for pattern in self.WARNING_PATTERNS:
            for match in re.finditer(pattern, self.raw_stdout + self.raw_stderr):
                group = match.group(1) if match.lastindex else match.group(0)
                if group and group.strip() not in self.warnings:
                    self.warnings.append(group.strip())

    def _parse_file_paths(self):
        # Match file paths (Unix and Windows)
        path_pattern = r'(?:/[\w\-\.]+)+/[\w\-\.]+|[A-Za-z]:\\[\w\-\\\.]+'
        for match in re.finditer(path_pattern, self.raw_stdout + self.raw_stderr):
            path = match.group(0)
            if path not in self.file_paths:
                self.file_paths.append(path)

    def _parse_urls(self):
        url_pattern = r'https?://[^\s<>"\']+'
        for match in re.finditer(url_pattern, self.raw_stdout + self.raw_stderr):
            url = match.group(0)
            if url not in self.urls:
                self.urls.append(url)

    def _parse_numbers(self):
        # Match integers and floats
        num_pattern = r'\b\d+\.?\d*\b'
        for match in re.finditer(num_pattern, self.raw_stdout):
            num = match.group(0)
            if num not in self.numbers:
                self.numbers.append(num)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "errors": self.errors,
            "warnings": self.warnings,
            "file_paths": self.file_paths,
            "urls": self.urls,
            "numbers": self.numbers,
            "raw_stdout": self.raw_stdout[:5000],
            "raw_stderr": self.raw_stderr[:5000],
        }


class Terminal:
    """
    Autonomous sandboxed terminal for command execution.

    Supports:
      - One-shot command execution with timeout
      - Interactive sessions maintaining state between commands
      - Working directory management
      - Environment variable handling
      - Shell session persistence
      - Integration with the sandbox for safe execution

    Usage:
        terminal = Terminal()

        # One-shot command
        result = await terminal.run("ls -la")

        # Interactive session
        session = terminal.create_session()
        await session.run("cd /tmp")
        await session.run("echo hello > test.txt")
        await session.run("cat test.txt")
        await session.close()
    """

    # Dangerous command patterns that should never be executed
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "mkfs.",
        "dd if=",
        ":(){ :|:& };:",
        "> /dev/sda",
        "chmod -R 777 /",
        "wget.*\\|.*sh",
        "curl.*\\|.*sh",
    ]

    # Maximum output size (5MB)
    MAX_OUTPUT_BYTES = 5 * 1024 * 1024

    def __init__(
        self,
        working_dir: Optional[str] = None,
        default_timeout: int = 60,
        env_vars: Optional[dict[str, str]] = None,
        sandbox_mode: bool = False,
    ):
        """
        Initialize the Terminal.

        Args:
            working_dir: Default working directory. Defaults to nexus_working_dir from config.
            default_timeout: Default command timeout in seconds.
            env_vars: Additional environment variables.
            sandbox_mode: If True, strip sensitive environment variables.
        """
        self.settings = get_settings()
        self.default_working_dir = working_dir or self.settings.nexus_working_dir
        self.default_timeout = default_timeout
        self._extra_env = env_vars or {}
        self._sandbox_mode = sandbox_mode
        self._sessions: dict[str, ShellSession] = {}

        # Ensure working directory exists
        Path(self.default_working_dir).mkdir(parents=True, exist_ok=True)

    def _check_command_safety(self, command: str) -> Optional[str]:
        """Check if a command contains dangerous patterns."""
        command_stripped = command.strip()
        for pattern in self.BLOCKED_COMMANDS:
            if re.search(pattern, command_stripped, re.IGNORECASE):
                return f"Command blocked for safety: matches pattern '{pattern}'"
        return None

    def _build_env(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        """Build the environment dictionary for command execution."""
        env = os.environ.copy()

        # Strip sensitive keys in sandbox mode
        if self._sandbox_mode:
            for key in [
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ZAI_API_KEY",
                "GOOGLE_API_KEY", "NEXUS_SECRET_KEY",
            ]:
                env.pop(key, None)

        # Apply extra environment variables
        env.update(self._extra_env)
        if extra:
            env.update(extra)

        return env

    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
        stdin: Optional[str] = None,
    ) -> CommandResult:
        """
        Execute a single command.

        Args:
            command: The shell command to execute.
            timeout: Timeout in seconds (default: self.default_timeout).
            working_dir: Working directory for the command.
            env_vars: Additional environment variables for this command.
            stdin: Optional stdin input for the command.

        Returns:
            CommandResult with execution output and metadata.

        Raises:
            SandboxError: If command contains dangerous patterns.
        """
        # Safety check
        danger = self._check_command_safety(command)
        if danger:
            raise SandboxError(reason=danger, command=command)

        effective_timeout = timeout or self.default_timeout
        effective_cwd = working_dir or self.default_working_dir
        env = self._build_env(env_vars)

        # Ensure working directory exists
        Path(effective_cwd).mkdir(parents=True, exist_ok=True)

        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                cwd=effective_cwd,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode() if stdin else None),
                    timeout=effective_timeout,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_bytes = b""
                stderr_bytes = f"Command timed out after {effective_timeout}s".encode()
                timed_out = True

            # Truncate large outputs
            stdout = stdout_bytes.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_BYTES]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_BYTES]

            return CommandResult(
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode if not timed_out else -1,
                timed_out=timed_out,
                execution_time_ms=(time.monotonic() - start) * 1000,
                working_dir=effective_cwd,
            )

        except Exception as exc:
            return CommandResult(
                command=command,
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=(time.monotonic() - start) * 1000,
                working_dir=effective_cwd,
            )

    async def run_parsed(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
    ) -> ParsedOutput:
        """
        Execute a command and return parsed output.

        Args:
            command: The shell command to execute.
            timeout: Timeout in seconds.
            working_dir: Working directory.
            env_vars: Additional environment variables.

        Returns:
            ParsedOutput with structured data extracted from the output.
        """
        result = await self.run(command, timeout, working_dir, env_vars)
        return ParsedOutput(
            raw_stdout=result.stdout,
            raw_stderr=result.stderr,
            exit_code=result.exit_code,
        )

    async def run_multiple(
        self,
        commands: list[str],
        timeout_per_command: Optional[int] = None,
        working_dir: Optional[str] = None,
        stop_on_error: bool = False,
    ) -> list[CommandResult]:
        """
        Execute multiple commands sequentially.

        Args:
            commands: List of commands to execute.
            timeout_per_command: Timeout per command.
            working_dir: Working directory for all commands.
            stop_on_error: Stop execution if a command fails.

        Returns:
            List of CommandResult for each command.
        """
        results: list[CommandResult] = []

        for cmd in commands:
            result = await self.run(cmd, timeout_per_command, working_dir)
            results.append(result)

            if stop_on_error and not result.success:
                logger.warning(
                    "Stopping command sequence: command failed (exit_code=%d): %s",
                    result.exit_code,
                    cmd[:100],
                )
                break

        return results

    def create_session(
        self,
        session_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> ShellSession:
        """
        Create an interactive shell session.

        The session maintains state (working directory, environment variables)
        between commands, similar to an interactive terminal session.

        Args:
            session_id: Optional session identifier. Auto-generated if not provided.
            working_dir: Initial working directory.
            env_vars: Session-specific environment variables.
            timeout: Default timeout for commands in this session.

        Returns:
            ShellSession instance for interactive command execution.
        """
        import uuid

        sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
        session = ShellSession(
            session_id=sid,
            terminal=self,
            working_dir=working_dir or self.default_working_dir,
            env_vars=env_vars or {},
            timeout=timeout or self.default_timeout,
        )
        self._sessions[sid] = session
        logger.info("Created shell session: %s", sid)
        return session

    def get_session(self, session_id: str) -> Optional[ShellSession]:
        """Get an existing shell session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active shell sessions."""
        return [
            {
                "session_id": s.session_id,
                "working_dir": s.working_dir,
                "command_count": s.command_count,
                "history_size": len(s.history),
            }
            for s in self._sessions.values()
        ]

    async def close_session(self, session_id: str) -> bool:
        """Close and remove a shell session."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.close()
            logger.info("Closed shell session: %s", session_id)
            return True
        return False

    async def close_all_sessions(self):
        """Close all active shell sessions."""
        for sid in list(self._sessions.keys()):
            await self.close_session(sid)


class ShellSession:
    """
    Interactive shell session with persistent state.

    Maintains working directory, environment variables, and command
    history across multiple command executions. Each command is
    executed in the context of the session's current state.

    Not a persistent process — state is tracked in Python and
    applied to each subprocess invocation.
    """

    def __init__(
        self,
        session_id: str,
        terminal: Terminal,
        working_dir: str,
        env_vars: dict[str, str],
        timeout: int,
    ):
        self.session_id = session_id
        self._terminal = terminal
        self.working_dir = working_dir
        self._env_vars = env_vars.copy()
        self.timeout = timeout
        self.history: list[CommandResult] = []
        self._closed = False

    @property
    def command_count(self) -> int:
        """Number of commands executed in this session."""
        return len(self.history)

    @property
    def last_result(self) -> Optional[CommandResult]:
        """Get the result of the last command."""
        return self.history[-1] if self.history else None

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        stdin: Optional[str] = None,
    ) -> CommandResult:
        """
        Execute a command in this session.

        The command runs in the session's working directory with
        the session's environment variables. If the command changes
        the directory (cd), the session's working_dir is updated.

        Args:
            command: The shell command to execute.
            timeout: Timeout in seconds (default: session timeout).
            stdin: Optional stdin input.

        Returns:
            CommandResult with execution output.

        Raises:
            SandboxError: If the session is closed or command is dangerous.
        """
        if self._closed:
            raise SandboxError(
                reason=f"Session {self.session_id} is closed",
                command=command,
            )

        effective_timeout = timeout or self.timeout

        # Handle cd commands specially to track working directory
        cd_match = re.match(r"^\s*cd\s+(.+?)(?:\s*&&\s*(.*))?$", command)
        if cd_match:
            target_dir = cd_match.group(1).strip()
            remaining = cd_match.group(2)

            # Resolve the target directory
            if os.path.isabs(target_dir):
                new_dir = target_dir
            else:
                new_dir = os.path.normpath(os.path.join(self.working_dir, target_dir))

            if os.path.isdir(new_dir):
                self.working_dir = new_dir
                logger.debug("Session %s: changed dir to %s", self.session_id, new_dir)
            else:
                result = CommandResult(
                    command=command,
                    stderr=f"cd: no such file or directory: {target_dir}",
                    exit_code=1,
                    working_dir=self.working_dir,
                )
                self.history.append(result)
                return result

            # If there's a remaining command after cd, execute it
            if remaining:
                return await self.run(remaining, timeout)

            result = CommandResult(
                command=command,
                stdout="",
                exit_code=0,
                working_dir=self.working_dir,
            )
            self.history.append(result)
            return result

        # Handle export/set commands for environment variables
        export_match = re.match(r"^\s*(?:export\s+)?(\w+)=(.+)$", command)
        if export_match and " " not in export_match.group(1):
            key = export_match.group(1)
            value = export_match.group(2).strip().strip("'\"")
            self._env_vars[key] = value
            logger.debug("Session %s: set env %s=%s", self.session_id, key, value)
            result = CommandResult(
                command=command,
                stdout="",
                exit_code=0,
                working_dir=self.working_dir,
            )
            self.history.append(result)
            return result

        # Execute the command in the session context
        result = await self._terminal.run(
            command=command,
            timeout=effective_timeout,
            working_dir=self.working_dir,
            env_vars=self._env_vars,
            stdin=stdin,
        )

        self.history.append(result)
        return result

    async def run_parsed(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> ParsedOutput:
        """
        Execute a command and return parsed output.

        Args:
            command: The shell command to execute.
            timeout: Timeout in seconds.

        Returns:
            ParsedOutput with structured data.
        """
        result = await self.run(command, timeout)
        return ParsedOutput(
            raw_stdout=result.stdout,
            raw_stderr=result.stderr,
            exit_code=result.exit_code,
        )

    def set_env(self, key: str, value: str):
        """Set an environment variable for this session."""
        self._env_vars[key] = value

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get an environment variable from this session."""
        return self._env_vars.get(key, default)

    def unset_env(self, key: str):
        """Remove an environment variable from this session."""
        self._env_vars.pop(key, None)

    def set_working_dir(self, path: str) -> bool:
        """
        Set the working directory for this session.

        Args:
            path: New working directory path.

        Returns:
            True if the directory was set successfully.
        """
        if os.path.isdir(path):
            self.working_dir = os.path.abspath(path)
            return True
        logger.warning("Session %s: directory does not exist: %s", self.session_id, path)
        return False

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get command history as a list of dicts."""
        return [r.to_dict() for r in self.history[-limit:]]

    async def close(self):
        """Close the session and clean up resources."""
        self._closed = True
        self._env_vars.clear()
        logger.info(
            "Session %s closed after %d commands",
            self.session_id,
            len(self.history),
        )
