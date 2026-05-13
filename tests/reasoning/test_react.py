"""
Tests for nexus.reasoning.react - Reasoning pattern selector.
"""

import pytest
from nexus.reasoning.react import (
    ReasoningPattern,
    select_reasoning_pattern,
    ReActLoop,
)


class TestReasoningPattern:
    """Test cases for ReasoningPattern enum."""

    def test_all_patterns(self):
        """All reasoning patterns should exist."""
        assert ReasoningPattern.REACT.value == "react"
        assert ReasoningPattern.TOT.value == "tree_of_thought"
        assert ReasoningPattern.LATS.value == "lats"


class TestSelectReasoningPattern:
    """Test cases for select_reasoning_pattern function."""

    def test_simple_task_returns_react(self):
        """Simple factual task returns ReAct."""
        pattern = select_reasoning_pattern("What is the capital of France?")
        assert pattern == ReasoningPattern.REACT

    def test_medium_complexity_hint(self):
        """Complexity hint overrides default selection."""
        pattern = select_reasoning_pattern("Some task", complexity="medium")
        assert pattern == ReasoningPattern.TOT

    def test_complex_complexity_hint(self):
        """Complex hint returns LATS."""
        pattern = select_reasoning_pattern("Task", complexity="complex")
        assert pattern == ReasoningPattern.LATS

    def test_simple_complexity_hint(self):
        """Simple hint returns ReAct."""
        pattern = select_reasoning_pattern("Task", complexity="simple")
        assert pattern == ReasoningPattern.REACT

    def test_explore_keyword_returns_lats(self):
        """Task with explore keyword returns LATS."""
        pattern = select_reasoning_pattern("Explore and optimize the best approach")
        assert pattern == ReasoningPattern.LATS

    def test_multiple_steps_returns_tot(self):
        """Task with multiple steps returns TOT."""
        pattern = select_reasoning_pattern("First do this, then do that, next do another thing")
        assert pattern == ReasoningPattern.TOT


class TestReActLoop:
    """Test cases for ReActLoop class."""

    def test_init(self):
        """ReActLoop initialization."""
        loop = ReActLoop()
        assert loop.max_steps == 10

    def test_reset(self):
        """Reset method."""
        loop = ReActLoop()
        loop.reset()
        assert loop.thoughts == []

    def test_thoughts_tracking(self):
        """Thoughts are tracked."""
        loop = ReActLoop()
        assert hasattr(loop, 'thoughts')
        assert hasattr(loop, 'actions')
        assert hasattr(loop, 'observations')