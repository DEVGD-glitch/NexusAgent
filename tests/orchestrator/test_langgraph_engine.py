"""
Tests for nexus.orchestrator.langgraph_engine.
"""

import pytest
from nexus.orchestrator.langgraph_engine import (
    NexusState,
    planner_node,
    executor_node,
    reflector_node,
)


class TestNexusState:
    """Test cases for NexusState TypedDict."""

    def test_empty_state(self):
        """Empty state creation."""
        state: NexusState = {}
        assert state == {}

    def test_state_with_required_fields(self):
        """State with required fields."""
        state: NexusState = {
            "task": "Test task",
            "iteration": 1
        }
        assert state["task"] == "Test task"
        assert state["iteration"] == 1

    def test_state_with_all_fields(self):
        """State with all fields."""
        state: NexusState = {
            "task": "Test task",
            "sub_tasks": ["step1", "step2"],
            "current_sub_task": "step1",
            "plan": "Plan text",
            "result": "Result text",
            "reflection": "Reflection text",
            "messages": [{"role": "user", "content": "test"}],
            "next_action": "execute",
            "iteration": 1,
            "metadata": {"key": "value"}
        }
        assert state["next_action"] == "execute"
        assert len(state["sub_tasks"]) == 2


class TestNodeFunctions:
    """Test cases for node functions."""

    @pytest.mark.asyncio
    async def test_planner_node_simple_task(self):
        """Planner node with simple task."""
        state: NexusState = {"task": "What is 2+2?", "iteration": 0}
        result = await planner_node(state)
        assert "plan" in result
        assert "sub_tasks" in result
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_planner_node_increments_iteration(self):
        """Planner node increments iteration."""
        state: NexusState = {"task": "Test task", "iteration": 3}
        result = await planner_node(state)
        assert result["iteration"] == 4

    @pytest.mark.asyncio
    async def test_executor_node_returns_result(self):
        """Executor node returns result."""
        state: NexusState = {"current_sub_task": "Test subtask", "messages": []}
        result = await executor_node(state)
        assert "result" in result

    @pytest.mark.asyncio
    async def test_reflector_node_exists(self):
        """Reflector node function exists."""
        assert callable(reflector_node)