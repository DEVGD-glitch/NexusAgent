"""
Tests for nexus.core.registry.
"""

import pytest
from nexus.core.registry import (
    AgentStatus,
    AgentCapability,
    AgentCard,
    AgentInstance,
    get_registry,
)


class TestAgentStatus:
    """Test cases for AgentStatus enum."""

    def test_all_statuses(self):
        """All agent statuses should exist."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.PAUSED.value == "paused"


class TestAgentCapability:
    """Test cases for AgentCapability enum."""

    def test_all_capabilities(self):
        """All capabilities should exist."""
        assert AgentCapability.RESEARCH.value == "research"
        assert AgentCapability.CODING.value == "coding"
        assert AgentCapability.ANALYSIS.value == "analysis"
        assert AgentCapability.OPERATION.value == "operation"


class TestAgentCard:
    """Test cases for AgentCard dataclass."""

    def test_default_creation(self):
        """AgentCard with defaults."""
        card = AgentCard(name="Test Agent", description="A test agent")
        assert card.name == "Test Agent"
        assert card.agent_id is not None
        assert card.version == "1.0.0"
        assert card.provider == "nexus"

    def test_to_dict(self):
        """Convert to dict."""
        card = AgentCard(name="Test")
        d = card.to_dict()
        assert "agent_id" in d
        assert "name" in d
        assert "capabilities" in d


class TestAgentInstance:
    """Test cases for AgentInstance dataclass."""

    def test_default_creation(self):
        """AgentInstance with defaults."""
        instance = AgentInstance(agent_type="coding", task="Write code")
        assert instance.agent_type == "coding"
        assert instance.instance_id is not None
        assert instance.status == AgentStatus.IDLE

    def test_with_status(self):
        """AgentInstance with custom status."""
        instance = AgentInstance(agent_type="test", status=AgentStatus.RUNNING)
        assert instance.status == AgentStatus.RUNNING


class TestGetRegistry:
    """Test cases for get_registry function."""

    def test_get_registry(self):
        """Get registry returns AgentRegistry."""
        registry = get_registry()
        assert registry is not None