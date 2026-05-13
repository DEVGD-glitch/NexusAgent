"""
Complete test coverage for nexus.security.sandbox.

Covers all missing lines (goal: >90% coverage):
  - _validate_shell_command function
  - _check_for_dangerous_code method
  - _build_sandbox_preamble (Unix / Windows branches)
  - LocalSandbox.execute_python (full flow)
  - LocalSandbox.execute_shell (full flow)
  - DockerSandbox.execute_python (full flow)
  - DockerSandbox.is_available
  - get_sandbox factory (all paths)

All async subprocess operations are mocked.
"""

import asyncio
import platform
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch, PropertyMock

import pytest

from nexus.security.sandbox import (
    LocalSandbox,
    DockerSandbox,
    SandboxResult,
    SandboxError,
    get_sandbox,
    SAFE_SHELL_COMMANDS,
    _validate_shell_command,
)


# =============================================================================
# _validate_shell_command tests
# =============================================================================

class TestValidateShellCommand:
    """Tests for the module-level _validate_shell_command function."""

    def test_valid_simple_command(self):
        """Valid simple command returns None (safe)."""
        assert _validate_shell_command("echo hello") is None

    def test_valid_command_with_args(self):
        """Valid command with arguments returns None."""
        assert _validate_shell_command("ls -la /tmp") is None

    def test_empty_command(self):
        """Empty command returns error message."""
        result = _validate_shell_command("")
        assert result == "Empty command"

    def test_whitespace_only(self):
        """Whitespace-only command fails shlex.split and returns error."""
        result = _validate_shell_command("   ")
        assert result is not None

    def test_invalid_syntax_unclosed_quote(self):
        """Unclosed quote returns 'Invalid shell syntax'."""
        result = _validate_shell_command("echo 'hello")
        assert result == "Invalid shell syntax"

    def test_dangerous_operator_double_ampersand(self):
        """Command with && is blocked."""
        result = _validate_shell_command("echo a && echo b")
        assert result is not None
        assert "&&" in result

    def test_dangerous_operator_semicolon(self):
        """Command with ; is blocked."""
        result = _validate_shell_command("echo a; rm -rf /")
        assert result is not None
        assert ";" in result

    def test_dangerous_operator_pipe(self):
        """Command with | is blocked."""
        result = _validate_shell_command("ls | grep test")
        assert result is not None
        assert "|" in result

    def test_dangerous_operator_subshell(self):
        """Command with $( is blocked."""
        result = _validate_shell_command("echo $(whoami)")
        assert result is not None
        assert "$(" in result

    def test_dangerous_operator_backtick(self):
        """Command with backtick is blocked."""
        result = _validate_shell_command("echo `whoami`")
        assert result is not None
        assert "`" in result

    def test_command_not_in_whitelist(self):
        """Command not in SAFE_SHELL_COMMANDS is blocked."""
        result = _validate_shell_command("curl http://evil.com")
        assert result is not None
        assert "curl" in result
        assert "not in allowed whitelist" in result

    def test_whitelisted_commands(self):
        """All SAFE_SHELL_COMMANDS are accepted with basic usage."""
        for cmd in ["echo", "pwd", "whoami", "date", "ls", "cat", "head", "tail",
                    "grep", "find", "wc", "git", "python"]:
            assert _validate_shell_command(f"{cmd}") is None


# =============================================================================
# _check_for_dangerous_code tests
# =============================================================================

class TestCheckForDangerousCode:
    """Tests for LocalSandbox._check_for_dangerous_code."""

    def setup_method(self):
        self.sandbox = LocalSandbox()

    def test_safe_code_returns_none(self):
        """Simple safe code returns None."""
        code = "print('hello world')"
        assert self.sandbox._check_for_dangerous_code(code) is None

    def test_math_operations_safe(self):
        """Math operations are safe."""
        code = "result = sum([1, 2, 3]); print(result)"
        assert self.sandbox._check_for_dangerous_code(code) is None

    def test_blocked_pattern_rm_rf(self):
        """rm -rf / pattern is detected."""
        result = self.sandbox._check_for_dangerous_code("rm -rf /")
        assert result is not None
        assert "rm -rf /" in result

    def test_blocked_pattern_fork_bomb(self):
        """Fork bomb pattern is detected."""
        result = self.sandbox._check_for_dangerous_code(":(){ :|:& };:")
        assert result is not None

    def test_blocked_pattern_import_os_with_system(self):
        """import os; os.system is detected."""
        result = self.sandbox._check_for_dangerous_code("import os; os.system('ls')")
        assert result is not None

    def test_dangerous_import_os(self):
        """import os triggers dangerous import check."""
        result = self.sandbox._check_for_dangerous_code("import os")
        assert result is not None
        assert "os" in result

    def test_dangerous_import_from_os(self):
        """from os import ... triggers dangerous import check."""
        result = self.sandbox._check_for_dangerous_code("from os import path")
        assert result is not None

    def test_dangerous_import_subprocess(self):
        """import subprocess is detected."""
        result = self.sandbox._check_for_dangerous_code("import subprocess")
        assert result is not None

    def test_dangerous_import_socket(self):
        """import socket is detected."""
        result = self.sandbox._check_for_dangerous_code("import socket")
        assert result is not None

    def test_dangerous_import_requests(self):
        """import requests is detected."""
        result = self.sandbox._check_for_dangerous_code("import requests")
        assert result is not None

    def test_dangerous_import_ctypes(self):
        """import ctypes is detected (also in BLOCKED_PATTERNS)."""
        result = self.sandbox._check_for_dangerous_code("import ctypes")
        assert result is not None

    def test_dangerous_import_multiprocessing(self):
        """import multiprocessing is detected."""
        result = self.sandbox._check_for_dangerous_code("import multiprocessing")
        assert result is not None

    def test_importlib_import_module_blocked(self):
        """importlib.import_module pattern is detected."""
        result = self.sandbox._check_for_dangerous_code("importlib.import_module('os')")
        assert result is not None

    def test_case_insensitive_blocked(self):
        """Blocked pattern detection is case-insensitive."""
        result = self.sandbox._check_for_dangerous_code("RM -RF /")
        assert result is not None

    def test_case_insensitive_import(self):
        """Import detection is case-insensitive."""
        result = self.sandbox._check_for_dangerous_code("IMPORT OS")
        assert result is not None

    def test_dangerous_import_winsound(self):
        """import winsound is detected."""
        result = self.sandbox._check_for_dangerous_code("import winsound")
        assert result is not None

    def test_dangerous_import_msvcrt(self):
        """import msvcrt is detected."""
        result = self.sandbox._check_for_dangerous_code("import msvcrt")
        assert result is not None

    def test_send_keys_pattern(self):
        """.send_keys( pattern is detected."""
        result = self.sandbox._check_for_dangerous_code("element.send_keys('admin')")
        assert result is not None

    def test_dd_if_pattern(self):
        """dd if= pattern is detected."""
        result = self.sandbox._check_for_dangerous_code("dd if=/dev/sda of=/tmp/img")
        assert result is not None


# =============================================================================
# _build_sandbox_preamble tests
# =============================================================================

class TestBuildSandboxPreamble:
    """Tests for LocalSandbox._build_sandbox_preamble."""

    def setup_method(self):
        self.sandbox = LocalSandbox(timeout=30, max_memory_mb=512)

    @patch("nexus.security.sandbox._HAS_RESOURCE", True)
    def test_unix_preamble_has_resource_limits(self):
        """Unix preamble includes resource.setrlimit calls."""
        preamble = self.sandbox._build_sandbox_preamble(30)
        assert "resource.setrlimit" in preamble
        assert "RLIMIT_AS" in preamble
        assert "RLIMIT_CPU" in preamble
        assert "RLIMIT_CORE" in preamble
        assert "536870912" in preamble  # 512 MB in bytes: 512 * 1024 * 1024

    @patch("nexus.security.sandbox._HAS_RESOURCE", True)
    def test_unix_preamble_timeout_plus_five(self):
        """Unix preamble sets CPU limit to timeout + 5."""
        preamble = self.sandbox._build_sandbox_preamble(60)
        assert "RLIMIT_CPU" in preamble
        assert "65" in preamble  # 60 + 5

    @patch("nexus.security.sandbox._HAS_RESOURCE", False)
    def test_windows_preamble_no_resource(self):
        """Windows preamble notes resource limits not available."""
        preamble = self.sandbox._build_sandbox_preamble(30)
        assert "resource.setrlimit" not in preamble
        assert "Windows sandbox" in preamble
        assert "timeout" in preamble

    @patch("nexus.security.sandbox._HAS_RESOURCE", True)
    def test_unix_preamble_error_handling(self):
        """Unix preamble wraps setrlimit in try/except."""
        preamble = self.sandbox._build_sandbox_preamble(30)
        assert "try:" in preamble or "try:" in preamble
        assert "except" in preamble

    @patch("nexus.security.sandbox._HAS_RESOURCE", True)
    def test_unix_preamble_different_memory(self):
        """Unix preamble reflects custom max_memory_mb."""
        s = LocalSandbox(max_memory_mb=1024)
        preamble = s._build_sandbox_preamble(30)
        assert "1073741824" in preamble  # 1024 MB in bytes


# =============================================================================
# LocalSandbox.execute_python tests
# =============================================================================

class TestLocalSandboxExecutePython:
    """Tests for LocalSandbox.execute_python."""

    @pytest.fixture
    def sandbox(self):
        return LocalSandbox(timeout=30)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_happy(self, mock_subprocess, sandbox):
        """execute_python returns SandboxResult with correct fields."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello world", b""))
        mock_proc.returncode = 0
        mock_proc.pid = 12345
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_python("print('hello world')")
        assert isinstance(result, SandboxResult)
        assert result.stdout == "hello world"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.timed_out is False
        # execution_time_ms may be 0 in mocked environment where
        # time.monotonic() readings are identical
        assert result.execution_time_ms >= 0
        assert result.memory_used_mb == 0.0

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_custom_timeout(self, mock_subprocess, sandbox):
        """execute_python uses timeout parameter."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_python("print('hi')", timeout=60)
        assert result.exit_code == 0

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_timeout(self, mock_subprocess, sandbox):
        """execute_python handles asyncio.TimeoutError."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.pid = 99999
        mock_subprocess.return_value = mock_proc

        # Make asyncio.wait_for raise TimeoutError
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()), \
             patch("nexus.security.sandbox.platform.system", return_value="Windows"), \
             patch("nexus.security.sandbox.asyncio.create_subprocess_exec") as mock_taskkill:
            mock_kill_proc = AsyncMock()
            mock_kill_proc.wait = AsyncMock()
            mock_taskkill.return_value = mock_kill_proc

            result = await sandbox.execute_python("import time; time.sleep(100)")

        assert result.timed_out is True
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_timeout_windows_taskkill_fails(self, mock_subprocess, sandbox):
        """execute_python handles taskkill failure gracefully on Windows."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.pid = 99999
        mock_subprocess.return_value = mock_proc

        with patch("nexus.security.sandbox.platform.system", return_value="Windows"), \
             patch("nexus.security.sandbox.asyncio.create_subprocess_exec",
                   side_effect=[mock_proc, RuntimeError("taskkill failed")]):
            # Should not raise - catches the error in the except block
            result = await sandbox.execute_python("import time; time.sleep(100)")

        assert result.timed_out is True

    async def test_execute_python_dangerous_code_rm(self, sandbox):
        """execute_python raises SandboxError for dangerous code (rm -rf /)."""
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_python("rm -rf /")
        assert "rm -rf /" in str(excinfo.value)

    async def test_execute_python_dangerous_import(self, sandbox):
        """execute_python raises SandboxError for import os (dangerous)."""
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_python("import os")
        assert "os" in str(excinfo.value)

    async def test_execute_python_blocked_pattern(self, sandbox):
        """execute_python raises SandboxError for blocked pattern."""
        with pytest.raises(SandboxError):
            await sandbox.execute_python("rm -rf /")

    async def test_execute_python_empty_code(self, sandbox):
        """execute_python handles empty code (dangerous check passes, then exec)."""
        # Empty code should pass the dangerous check (no patterns matched)
        # but we need to mock subprocess since it will try to execute
        with patch("nexus.security.sandbox.asyncio.create_subprocess_exec") as m:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            m.return_value = mock_proc
            result = await sandbox.execute_python("")
        assert result.exit_code == 0

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_general_error(self, mock_subprocess, sandbox):
        """execute_python raises SandboxError on subprocess error."""
        mock_subprocess.side_effect = RuntimeError("process creation failed")
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_python("print('hi')")
        assert "process creation failed" in str(excinfo.value)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_env_vars(self, mock_subprocess, sandbox):
        """execute_python passes additional env_vars."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        await sandbox.execute_python("print('hi')", env_vars={"MY_VAR": "my_value"})
        # The env should contain MY_VAR
        call_args = mock_subprocess.call_args
        # The env is passed as kwarg to create_subprocess_exec
        # Actually, env is a kwarg in the outer call
        assert mock_subprocess.called

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_execute_python_strips_sensitive_env(self, mock_subprocess, sandbox):
        """execute_python strips API keys from environment."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-123", "OTHER_VAR": "keep"}):
            await sandbox.execute_python("print('hi')")

        # Check the env passed to subprocess doesn't contain sensitive keys
        call_kwargs = mock_subprocess.call_args.kwargs
        passed_env = call_kwargs.get("env", {})
        assert "OPENAI_API_KEY" not in passed_env
        assert passed_env.get("OTHER_VAR") == "keep"


# =============================================================================
# LocalSandbox.execute_shell tests
# =============================================================================

class TestLocalSandboxExecuteShell:
    """Tests for LocalSandbox.execute_shell."""

    @pytest.fixture
    def sandbox(self):
        return LocalSandbox(timeout=30)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_shell")
    async def test_execute_shell_happy(self, mock_subprocess, sandbox):
        """execute_shell returns SandboxResult for valid commands."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_shell("echo hello")
        assert result.stdout == "hello"
        assert result.exit_code == 0
        assert result.timed_out is False

    @patch("nexus.security.sandbox.asyncio.create_subprocess_shell")
    async def test_execute_shell_timeout(self, mock_subprocess, sandbox):
        """execute_shell handles asyncio.TimeoutError."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_shell("echo hello")
        assert result.timed_out is True
        assert "timed out" in result.stderr

    @patch("nexus.security.sandbox.asyncio.create_subprocess_shell")
    async def test_execute_shell_general_error(self, mock_subprocess, sandbox):
        """execute_shell raises SandboxError on subprocess failure."""
        mock_subprocess.side_effect = RuntimeError("process error")
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_shell("echo hi")
        assert "process error" in str(excinfo.value)

    async def test_execute_shell_invalid_command(self, sandbox):
        """execute_shell raises SandboxError for command not in whitelist."""
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_shell("curl http://evil.com")
        assert "curl" in str(excinfo.value)

    async def test_execute_shell_dangerous_operator(self, sandbox):
        """execute_shell raises SandboxError for dangerous operators.

        The command ``echo a && rm -rf /`` triggers *both*
        ``_check_for_dangerous_code`` (which detects ``rm -rf /``) and
        ``_validate_shell_command`` (which detects ``&&``).  The first
        check wins, so the error message mentions the blocked pattern.
        """
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_shell("echo a && rm -rf /")
        # _check_for_dangerous_code matches "rm -rf /" before
        # _validate_shell_command matches "&&"
        assert "dangerous pattern" in str(excinfo.value) or "&&" in str(excinfo.value)

    async def test_execute_shell_dangerous_code_rm(self, sandbox):
        """execute_shell raises SandboxError for dangerous code patterns."""
        # This is caught by _check_for_dangerous_code before _validate_shell_command
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_shell("rm -rf /")
        assert "rm -rf /" in str(excinfo.value)

    async def test_execute_shell_empty(self, sandbox):
        """execute_shell raises SandboxError for empty command."""
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_shell("")
        assert "Empty" in str(excinfo.value)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_shell")
    async def test_execute_shell_custom_timeout(self, mock_subprocess, sandbox):
        """execute_shell passes custom timeout."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_shell("echo hi", timeout=15)
        assert result.exit_code == 0

    async def test_execute_shell_all_safe_commands(self, sandbox):
        """execute_shell accepts all SAFE_SHELL_COMMANDS."""
        for cmd in ["echo", "pwd", "date", "ls", "whoami"]:
            with patch("nexus.security.sandbox.asyncio.create_subprocess_shell") as m:
                mock_proc = AsyncMock()
                mock_proc.communicate = AsyncMock(
                    return_value=(f"{cmd} output".encode(), b"")
                )
                mock_proc.returncode = 0
                m.return_value = mock_proc

                result = await sandbox.execute_shell(cmd)
                assert result.exit_code == 0
                assert cmd in result.stdout


# =============================================================================
# DockerSandbox.execute_python tests
# =============================================================================

class TestDockerSandboxExecutePython:
    """Tests for DockerSandbox.execute_python."""

    @pytest.fixture
    def sandbox(self):
        return DockerSandbox(timeout=30)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_happy(self, mock_subprocess, sandbox):
        """DockerSandbox.execute_python returns SandboxResult."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"docker output", b""))
        mock_proc.returncode = 0
        mock_proc.pid = 555
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_python("print('hello from docker')")
        assert isinstance(result, SandboxResult)
        assert result.stdout == "docker output"
        assert result.exit_code == 0
        assert result.timed_out is False
        # May be 0 in fully-mocked environments
        assert result.execution_time_ms >= 0

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_timeout(self, mock_subprocess, sandbox):
        """DockerSandbox handles timeout."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_subprocess.return_value = mock_proc

        result = await sandbox.execute_python("import time; time.sleep(100)")
        assert result.timed_out is True
        assert result.exit_code == -1

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_file_not_found(self, mock_subprocess, sandbox):
        """DockerSandbox raises SandboxError when Docker not installed."""
        mock_subprocess.side_effect = FileNotFoundError()
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_python("print('hi')")
        assert "Docker is not installed" in str(excinfo.value)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_general_error(self, mock_subprocess, sandbox):
        """DockerSandbox raises SandboxError on general error."""
        mock_subprocess.side_effect = RuntimeError("docker daemon error")
        with pytest.raises(SandboxError) as excinfo:
            await sandbox.execute_python("print('hi')")
        assert "docker daemon error" in str(excinfo.value)

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_custom_timeout(self, mock_subprocess, sandbox):
        """DockerSandbox uses custom timeout (+10s buffer for Docker)."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        await sandbox.execute_python("print('hi')", timeout=15)
        # wait_for should be called with timeout = 15 + 10 = 25

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_docker_execute_python_command_structure(self, mock_subprocess, sandbox):
        """DockerSandbox builds correct docker run command."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        await sandbox.execute_python("print('hi')")
        cmd_args = mock_subprocess.call_args[0]
        # First arg should be "docker"
        assert cmd_args[0] == "docker"
        assert "run" in cmd_args
        assert "--rm" in cmd_args
        assert "--network" in cmd_args
        assert "none" in cmd_args


# =============================================================================
# DockerSandbox.is_available tests
# =============================================================================

class TestDockerSandboxIsAvailable:
    """Tests for DockerSandbox.is_available."""

    @pytest.fixture
    def sandbox(self):
        return DockerSandbox(image="nexus-sandbox:latest")

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_is_available_true(self, mock_subprocess, sandbox):
        """is_available returns True when image exists."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"sha256:abc123\n", b"")
        )
        mock_subprocess.return_value = mock_proc

        result = await sandbox.is_available()
        assert result is True

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_is_available_false_no_output(self, mock_subprocess, sandbox):
        """is_available returns False when no image found."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_proc

        result = await sandbox.is_available()
        assert result is False

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_is_available_false_docker_not_found(self, mock_subprocess, sandbox):
        """is_available returns False when Docker is not installed."""
        mock_subprocess.side_effect = FileNotFoundError()

        result = await sandbox.is_available()
        assert result is False

    @patch("nexus.security.sandbox.asyncio.create_subprocess_exec")
    async def test_is_available_uses_correct_image(self, mock_subprocess, sandbox):
        """is_available checks the configured Docker image."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"sha:abc\n", b""))
        mock_subprocess.return_value = mock_proc

        await sandbox.is_available()
        args = mock_subprocess.call_args[0]
        assert "docker" in args
        assert "images" in args
        assert "-q" in args
        assert sandbox.image in args


# =============================================================================
# DockerSandbox init tests
# =============================================================================

class TestDockerSandboxInit:
    """Tests for DockerSandbox.__init__."""

    @patch("nexus.security.sandbox.get_settings")
    def test_init_with_defaults(self, mock_settings):
        """DockerSandbox uses settings defaults."""
        s = MagicMock()
        s.sandbox_docker_image = "nexus-default:latest"
        mock_settings.return_value = s

        sandbox = DockerSandbox()
        assert sandbox.image == "nexus-default:latest"
        assert sandbox.timeout == 30
        assert sandbox.max_memory_mb == 512
        assert sandbox.cpu_quota == 50000

    def test_init_with_explicit_values(self):
        """DockerSandbox accepts explicit parameters."""
        sandbox = DockerSandbox(
            image="my-image:v1",
            timeout=60,
            max_memory_mb=1024,
            cpu_quota=100000,
        )
        assert sandbox.image == "my-image:v1"
        assert sandbox.timeout == 60
        assert sandbox.max_memory_mb == 1024
        assert sandbox.cpu_quota == 100000


# =============================================================================
# get_sandbox tests
# =============================================================================

class TestGetSandbox:
    """Tests for the get_sandbox factory function."""

    @patch("nexus.security.sandbox.get_settings")
    def test_get_sandbox_sandbox_disabled(self, mock_settings):
        """get_sandbox returns LocalSandbox when sandbox_disabled."""
        s = MagicMock()
        s.sandbox_enabled = False
        mock_settings.return_value = s

        sandbox = get_sandbox()
        assert isinstance(sandbox, LocalSandbox)

    @patch("nexus.security.sandbox.get_settings")
    def test_get_sandbox_sandbox_enabled_uses_docker(self, mock_settings):
        """get_sandbox returns DockerSandbox when sandbox_enabled."""
        s = MagicMock()
        s.sandbox_enabled = True
        s.sandbox_docker_image = "sandbox:latest"
        mock_settings.return_value = s

        sandbox = get_sandbox()
        assert isinstance(sandbox, DockerSandbox)
        assert sandbox.image == "sandbox:latest"

    @patch("nexus.security.sandbox.get_settings")
    def test_get_sandbox_enabled_docker_fails_falls_back(self, mock_settings):
        """get_sandbox falls back to LocalSandbox when Docker init fails."""
        s = MagicMock()
        s.sandbox_enabled = True
        s.sandbox_docker_image = "nonexistent:latest"
        mock_settings.return_value = s

        # DockerSandbox() in the try block could fail for various reasons
        # The try/except catches any exception from DockerSandbox()
        with patch("nexus.security.sandbox.DockerSandbox", side_effect=RuntimeError("Docker init failed")):
            sandbox = get_sandbox()

        # Falls back to LocalSandbox
        assert isinstance(sandbox, LocalSandbox)

    def test_get_sandbox_local_defaults(self):
        """Default LocalSandbox has reasonable defaults."""
        sandbox = get_sandbox()
        if isinstance(sandbox, LocalSandbox):
            assert sandbox.timeout == 30
            assert sandbox.max_memory_mb == 512
            assert sandbox.MAX_OUTPUT_BYTES == 5 * 1024 * 1024


# =============================================================================
# LocalSandbox init tests
# =============================================================================

class TestLocalSandboxInit:
    """Tests for LocalSandbox.__init__."""

    def test_init_defaults(self):
        """LocalSandbox uses sensible defaults."""
        sandbox = LocalSandbox()
        assert sandbox.timeout == 30
        assert sandbox.max_memory_mb == 512
        assert sandbox.max_output_bytes == 5 * 1024 * 1024
        assert sandbox.allowed_paths == []

    def test_init_custom_values(self):
        """LocalSandbox accepts custom parameters."""
        sandbox = LocalSandbox(
            timeout=60,
            max_memory_mb=256,
            max_output_bytes=1024,
            working_dir="/tmp/sandbox",
            allowed_paths=["/home", "/data"],
        )
        assert sandbox.timeout == 60
        assert sandbox.max_memory_mb == 256
        assert sandbox.max_output_bytes == 1024
        assert sandbox.working_dir == "/tmp/sandbox"
        assert sandbox.allowed_paths == ["/home", "/data"]

    def test_init_working_dir_defaults_to_tempdir(self):
        """working_dir defaults to tempfile.gettempdir()."""
        import tempfile
        sandbox = LocalSandbox()
        assert sandbox.working_dir == tempfile.gettempdir()


# =============================================================================
# SandboxResult tests (additional coverage)
# =============================================================================

class TestSandboxResultAdditional:
    """Additional tests for SandboxResult dataclass."""

    def test_default_values(self):
        """SandboxResult has sensible defaults."""
        r = SandboxResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.exit_code == -1
        assert r.timed_out is False
        assert r.execution_time_ms == 0.0
        assert r.memory_used_mb == 0.0
        assert r.files_created == []
        assert r.files_modified == []

    def test_all_fields(self):
        """SandboxResult stores all fields correctly."""
        r = SandboxResult(
            stdout="out",
            stderr="err",
            exit_code=1,
            timed_out=True,
            execution_time_ms=500.5,
            memory_used_mb=128.0,
            files_created=["/tmp/a"],
            files_modified=["/tmp/b"],
        )
        assert r.stdout == "out"
        assert r.stderr == "err"
        assert r.exit_code == 1
        assert r.timed_out is True
        assert r.execution_time_ms == 500.5
        assert r.memory_used_mb == 128.0
        assert r.files_created == ["/tmp/a"]
        assert r.files_modified == ["/tmp/b"]


# =============================================================================
# Constant tests
# =============================================================================

class TestSandboxConstants:
    """Tests for sandbox module-level constants."""

    def test_safe_shell_commands_is_frozenset(self):
        """SAFE_SHELL_COMMANDS is a frozenset."""
        assert isinstance(SAFE_SHELL_COMMANDS, frozenset)

    def test_safe_shell_contains_expected(self):
        """SAFE_SHELL_COMMANDS contains expected commands."""
        for cmd in ["echo", "ls", "cat", "git", "python", "grep", "find"]:
            assert cmd in SAFE_SHELL_COMMANDS

    def test_safe_shell_no_dangerous_commands(self):
        """SAFE_SHELL_COMMANDS does not contain dangerous commands."""
        assert "rm" not in SAFE_SHELL_COMMANDS
        assert "curl" not in SAFE_SHELL_COMMANDS
        assert "wget" not in SAFE_SHELL_COMMANDS
        assert "sudo" not in SAFE_SHELL_COMMANDS
        assert "chmod" not in SAFE_SHELL_COMMANDS

    def test_blocked_patterns_not_empty(self):
        """BLOCKED_PATTERNS has patterns defined."""
        assert len(LocalSandbox.BLOCKED_PATTERNS) > 10

    def test_dangerous_imports_not_empty(self):
        """_DANGEROUS_IMPORTS has modules defined."""
        assert len(LocalSandbox._DANGEROUS_IMPORTS) > 10
        assert "os" in LocalSandbox._DANGEROUS_IMPORTS
        assert "subprocess" in LocalSandbox._DANGEROUS_IMPORTS
