"""
Tests for nexus.orchestrator.patterns.
"""

import pytest
from nexus.orchestrator.patterns import PatternType, AgentTask, PatternResult


class TestPatternType:
    """Test cases for PatternType enum."""

    def test_all_patterns(self):
        """All pattern types should exist."""
        assert PatternType.SUPERVISOR.value == "supervisor"
        assert PatternType.PIPELINE.value == "pipeline"
        assert PatternType.PARALLEL.value == "parallel"
        assert PatternType.HIERARCHICAL.value == "hierarchical"
        assert PatternType.MESH.value == "mesh"
        assert PatternType.SWARM.value == "swarm"


class TestAgentTask:
    """Test cases for AgentTask."""

    def test_creation_with_defaults(self):
        """AgentTask with default values."""
        task = AgentTask(description="Test task")
        assert task.description == "Test task"
        assert task.task_id is not None
        assert task.status == "pending"

    def test_creation_with_all_fields(self):
        """AgentTask with all fields."""
        task = AgentTask(
            description="Test",
            assigned_to="agent1",
            status="completed",
            result="Success",
            dependencies=["dep1"]
        )
        assert task.assigned_to == "agent1"
        assert task.status == "completed"
        assert task.result == "Success"


class TestPatternResult:
    """Test cases for PatternResult."""

    def test_creation(self):
        """PatternResult creation."""
        result = PatternResult(
            pattern=PatternType.PIPELINE,
            success=True,
            results=[{"output": "test"}]
        )
        assert result.pattern == PatternType.PIPELINE
        assert result.success is True

    def test_creation_with_counts(self):
        """PatternResult with task counts."""
        result = PatternResult(
            pattern=PatternType.PARALLEL,
            success=True,
            total_tasks=5,
            completed_tasks=4,
            failed_tasks=1
        )
        assert result.total_tasks == 5
        assert result.completed_tasks == 4
        assert result.failed_tasks == 1