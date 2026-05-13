"""
Tests for nexus.memory.orchestrator.
"""

import pytest
from nexus.memory.orchestrator import (
    MemoryType,
    MemoryContext,
    MemoryResult,
    MemoryOrchestrator,
)


class TestMemoryType:
    """Test cases for MemoryType enum."""

    def test_all_types(self):
        """All memory types should exist."""
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.IDENTITY.value == "identity"


class TestMemoryContext:
    """Test cases for MemoryContext dataclass."""

    def test_default_creation(self):
        """Default context."""
        ctx = MemoryContext(task="Test task")
        assert ctx.task == "Test task"
        assert ctx.task_type == "general"
        assert ctx.priority == 1.0

    def test_full_creation(self):
        """Full context with all fields."""
        ctx = MemoryContext(
            task="Debug error",
            task_type="debugging",
            user_id="user1",
            session_id="session1",
            priority=0.8,
            ttl_seconds=3600
        )
        assert ctx.task_type == "debugging"
        assert ctx.user_id == "user1"
        assert ctx.ttl_seconds == 3600


class TestMemoryResult:
    """Test cases for MemoryResult dataclass."""

    def test_creation(self):
        """Result creation."""
        result = MemoryResult(
            memory_type=MemoryType.EPISODIC,
            content="Some content",
            relevance_score=0.9
        )
        assert result.memory_type == MemoryType.EPISODIC
        assert result.content == "Some content"
        assert result.relevance_score == 0.9


class TestMemoryOrchestrator:
    """Test cases for MemoryOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        return MemoryOrchestrator()

    def test_init(self, orchestrator):
        """Orchestrator initialization."""
        assert orchestrator is not None

    def test_detect_working_memory(self):
        """Detects working memory type."""
        orchestrator = MemoryOrchestrator()
        ctx = MemoryContext(task="current context", task_type="conversation")
        mem_type = orchestrator._detect_memory_type(ctx)
        assert mem_type == MemoryType.WORKING

    def test_detect_episodic_memory(self):
        """Detects episodic memory type."""
        orchestrator = MemoryOrchestrator()
        ctx = MemoryContext(task="what happened yesterday", task_type="general")
        mem_type = orchestrator._detect_memory_type(ctx)
        assert mem_type == MemoryType.EPISODIC

    def test_detect_semantic_memory(self):
        """Detects semantic memory type."""
        orchestrator = MemoryOrchestrator()
        ctx = MemoryContext(task="explain what is a neural network", task_type="research")
        mem_type = orchestrator._detect_memory_type(ctx)
        assert mem_type == MemoryType.SEMANTIC