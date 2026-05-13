"""
Tests for nexus.security.audit - AuditLogger, AuditEntry.
"""

import pytest
from nexus.security.audit import AuditLogger, AuditEntry, AuditLevel, AuditCategory


class TestAuditLogger:
    """Test cases for AuditLogger."""

    @pytest.fixture
    def logger(self):
        return AuditLogger()

    def test_init(self, logger):
        assert logger is not None

    def test_log_returns_event_id(self, logger):
        """Log should return event_id string."""
        event_id = logger.log(
            category=AuditCategory.AGENT_ACTION,
            action="test_action",
            target="test_target",
            details={"key": "value"},
            outcome="success"
        )
        assert isinstance(event_id, str)
        assert len(event_id) > 0

    def test_log_with_defaults(self, logger):
        """Log with minimal parameters."""
        event_id = logger.log(category=AuditCategory.TOOL_CALL, action="execute")
        assert isinstance(event_id, str)


class TestAuditEntry:
    """Test cases for AuditEntry."""

    def test_creation_with_defaults(self):
        """AuditEntry with default values."""
        entry = AuditEntry(action="test")
        assert entry.action == "test"
        assert entry.event_id is not None
        assert entry.timestamp is not None

    def test_creation_with_all_fields(self):
        """AuditEntry with all fields."""
        entry = AuditEntry(
            action="test",
            category=AuditCategory.SECURITY,
            level=AuditLevel.WARNING,
            actor="user1",
            target="file.txt",
            outcome="success"
        )
        assert entry.action == "test"
        assert entry.category == AuditCategory.SECURITY
        assert entry.level == AuditLevel.WARNING

    def test_to_json(self):
        """Convert entry to JSON."""
        entry = AuditEntry(action="test", category=AuditCategory.AUTH)
        json_str = entry.to_json()
        assert isinstance(json_str, str)
        assert '"action": "test"' in json_str


class TestAuditLevel:
    """Test cases for AuditLevel enum."""

    def test_all_levels(self):
        """All audit levels should exist."""
        assert AuditLevel.DEBUG.value == "debug"
        assert AuditLevel.INFO.value == "info"
        assert AuditLevel.WARNING.value == "warning"
        assert AuditLevel.CRITICAL.value == "critical"


class TestAuditCategory:
    """Test cases for AuditCategory enum."""

    def test_all_categories(self):
        """All audit categories should exist."""
        assert AuditCategory.AUTH.value == "auth"
        assert AuditCategory.TOOL_CALL.value == "tool_call"
        assert AuditCategory.MEMORY_ACCESS.value == "memory_access"
        assert AuditCategory.CODE_EXECUTION.value == "code_execution"
        assert AuditCategory.LLM_CALL.value == "llm_call"
        assert AuditCategory.CONFIG_CHANGE.value == "config_change"
        assert AuditCategory.AGENT_ACTION.value == "agent_action"
        assert AuditCategory.DATA_ACCESS.value == "data_access"
        assert AuditCategory.SECURITY.value == "security"