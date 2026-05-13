"""
Tests for nexus.core.exceptions.
"""

import pytest
from nexus.core.exceptions import (
    NexusError,
    ConfigurationError,
    MissingAPIKeyError,
    NexusMemoryError,
    MemoryStoreError,
    MemorySearchError,
    OrchestratorError,
    LLMError,
    SecurityError,
    AgentError,
)


class TestNexusError:
    """Test cases for base NexusError."""

    def test_creation_basic(self):
        """Basic error creation."""
        error = NexusError("Test error")
        assert error.message == "Test error"
        assert error.code == "NEXUS_ERROR"

    def test_creation_with_code(self):
        """Error with custom code."""
        error = NexusError("Test error", code="CUSTOM_CODE")
        assert error.code == "CUSTOM_CODE"

    def test_creation_with_details(self):
        """Error with details."""
        error = NexusError("Test error", details={"key": "value"})
        assert error.details["key"] == "value"

    def test_to_dict(self):
        """Convert to dict."""
        error = NexusError("Test error", code="ERR", details={"a": 1})
        d = error.to_dict()
        assert d["error"] == "ERR"
        assert d["message"] == "Test error"
        assert d["details"]["a"] == 1


class TestConfigurationError:
    """Test cases for ConfigurationError."""

    def test_creation(self):
        """Configuration error creation."""
        error = ConfigurationError("Missing config")
        assert error.code == "CONFIG_ERROR"


class TestMissingAPIKeyError:
    """Test cases for MissingAPIKeyError."""

    def test_creation(self):
        """Missing API key error."""
        error = MissingAPIKeyError("openai", "OPENAI_API_KEY")
        assert "openai" in error.message
        assert "OPENAI_API_KEY" in error.message
        assert error.code == "MISSING_API_KEY"


class TestNexusMemoryError:
    """Test cases for NexusMemoryError."""

    def test_creation(self):
        """Memory error creation."""
        error = NexusMemoryError("Memory failed")
        assert error.code == "MEMORY_ERROR"


class TestMemoryStoreError:
    """Test cases for MemoryStoreError."""

    def test_creation(self):
        """Memory store error."""
        error = MemoryStoreError("test_ns", "Connection failed")
        assert "test_ns" in error.message
        assert error.code == "MEMORY_STORE_ERROR"


class TestMemorySearchError:
    """Test cases for MemorySearchError."""

    def test_creation(self):
        """Memory search error."""
        error = MemorySearchError("test_ns", "Query timeout")
        assert "test_ns" in error.message


class TestOrchestratorError:
    """Test cases for OrchestratorError."""

    def test_creation(self):
        """Orchestrator error creation."""
        error = OrchestratorError("Task failed")
        assert "Task failed" in str(error)


class TestLLMError:
    """Test cases for LLMError."""

    def test_creation(self):
        """LLM error creation."""
        error = LLMError("Provider failed")
        assert error.code == "LLM_ERROR"


class TestSecurityError:
    """Test cases for SecurityError."""

    def test_creation(self):
        """Security error creation."""
        error = SecurityError("Access denied")
        assert error.code == "SECURITY_ERROR"


class TestAgentError:
    """Test cases for AgentError."""

    def test_creation(self):
        """Agent error creation."""
        error = AgentError("Agent crashed")
        assert error.code == "AGENT_ERROR"