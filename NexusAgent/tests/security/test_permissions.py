"""
Tests for nexus.security.permissions - PermissionManager.
"""

import pytest
from nexus.security.permissions import (
    PermissionManager,
    PermissionAction,
    PermissionResult,
    PermissionMode,
    PermissionRequest,
    ALWAYS_CONFIRM,
)


class TestPermissionManager:
    """Test cases for PermissionManager."""

    @pytest.fixture
    def manager(self):
        return PermissionManager()

    def test_init(self, manager):
        assert manager is not None


class TestPermissionAction:
    """Test cases for PermissionAction enum."""

    def test_all_actions(self):
        """All permission actions should exist."""
        assert PermissionAction.DELETE_FILE.value == "delete_file"
        assert PermissionAction.WRITE_FILE_SYSTEM.value == "write_file_system"
        assert PermissionAction.EXECUTE_CODE.value == "execute_code"
        assert PermissionAction.EXECUTE_SHELL.value == "execute_shell"
        assert PermissionAction.WRITE_OUTSIDE_WORKSPACE.value == "write_outside_workspace"
        assert PermissionAction.NETWORK_REQUEST.value == "network_request"
        assert PermissionAction.INSTALL_PACKAGE.value == "install_package"
        assert PermissionAction.RESET_MEMORY.value == "reset_memory"
        assert PermissionAction.DELETE_MEMORY.value == "delete_memory"


class TestPermissionResult:
    """Test cases for PermissionResult."""

    def test_granted_result(self):
        """Granted result."""
        result = PermissionResult(granted=True, reason="Allowed")
        assert result.granted is True

    def test_denied_result(self):
        """Denied result."""
        result = PermissionResult(granted=False, reason="Access denied")
        assert result.granted is False
        assert result.reason == "Access denied"


class TestPermissionMode:
    """Test cases for PermissionMode enum."""

    def test_all_modes(self):
        """All permission modes should exist."""
        assert PermissionMode.AUTO.value == "auto"
        assert PermissionMode.CONFIRM.value == "confirm"


class TestPermissionRequest:
    """Test cases for PermissionRequest."""

    def test_request_creation(self):
        """Create a permission request."""
        req = PermissionRequest(
            action=PermissionAction.DELETE_FILE,
            description="Delete file",
            target="/path/to/file"
        )
        assert req.action == PermissionAction.DELETE_FILE
        assert req.target == "/path/to/file"


class TestALWAYS_CONFIRM:
    """Test cases for ALWAYS_CONFIRM constant."""

    def test_contains_dangerous_actions(self):
        """ALWAYS_CONFIRM should contain dangerous actions."""
        assert PermissionAction.DELETE_FILE in ALWAYS_CONFIRM
        assert PermissionAction.EXECUTE_CODE in ALWAYS_CONFIRM
        assert PermissionAction.EXECUTE_SHELL in ALWAYS_CONFIRM
        assert PermissionAction.WRITE_OUTSIDE_WORKSPACE in ALWAYS_CONFIRM