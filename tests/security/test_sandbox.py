"""
Tests for nexus.security.sandbox - LocalSandbox.
"""

import pytest
from nexus.security.sandbox import (
    LocalSandbox,
    SandboxResult,
    SandboxError,
    get_sandbox,
    SAFE_SHELL_COMMANDS,
)


class TestLocalSandbox:
    """Test cases for LocalSandbox."""

    @pytest.fixture
    def sandbox(self):
        return LocalSandbox()

    def test_init(self, sandbox):
        assert sandbox is not None


class TestSAFE_SHELL_COMMANDS:
    """Test cases for SAFE_SHELL_COMMANDS constant."""

    def test_is_frozenset(self):
        """Should be a frozenset."""
        assert isinstance(SAFE_SHELL_COMMANDS, frozenset)

    def test_contains_echo(self):
        """Should contain echo."""
        assert "echo" in SAFE_SHELL_COMMANDS

    def test_contains_ls(self):
        """Should contain ls."""
        assert "ls" in SAFE_SHELL_COMMANDS

    def test_contains_python(self):
        """Should contain python."""
        assert "python" in SAFE_SHELL_COMMANDS


class TestSandboxResult:
    """Test cases for SandboxResult."""

    def test_success_result(self):
        """Successful execution result."""
        result = SandboxResult(
            stdout="output",
            stderr="",
            exit_code=0,
            execution_time_ms=100.0
        )
        assert result.stdout == "output"
        assert result.exit_code == 0

    def test_error_result(self):
        """Error execution result."""
        result = SandboxResult(
            stdout="",
            stderr="Error message",
            exit_code=1,
            execution_time_ms=50.0
        )
        assert result.stderr == "Error message"
        assert result.exit_code == 1


class TestSandboxError:
    """Test cases for SandboxError."""

    def test_error_creation(self):
        """SandboxError creation."""
        error = SandboxError("Test error")
        assert "Test error" in str(error)


class TestGetSandbox:
    """Test cases for get_sandbox function."""

    def test_returns_sandbox(self):
        """get_sandbox should return a sandbox instance."""
        sandbox = get_sandbox()
        assert sandbox is not None