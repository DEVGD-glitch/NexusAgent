"""
Tests for nexus.reasoning.tot - Tree-of-Thought.
"""

import pytest
from nexus.reasoning.tot import (
    ThoughtNode,
    ToTResult,
    TreeOfThought,
)


class TestThoughtNode:
    """Test cases for ThoughtNode dataclass."""

    def test_creation_with_defaults(self):
        """ThoughtNode with defaults."""
        node = ThoughtNode(thought="Test thought")
        assert node.thought == "Test thought"
        assert node.score == 0.0
        assert node.depth == 0
        assert node.children == []
        assert node.parent is None
        assert node.is_solution is False

    def test_creation_with_all_fields(self):
        """ThoughtNode with all fields."""
        node = ThoughtNode(
            thought="Complex thought",
            score=8.5,
            depth=3,
            is_solution=True,
            evaluation="Good solution"
        )
        assert node.score == 8.5
        assert node.depth == 3
        assert node.is_solution is True

    def test_to_dict(self):
        """Convert to dict."""
        node = ThoughtNode(thought="Test", score=7.0, depth=2)
        d = node.to_dict()
        assert "thought" in d
        assert "score" in d
        assert "depth" in d
        assert d["children_count"] == 0


class TestToTResult:
    """Test cases for ToTResult dataclass."""

    def test_creation(self):
        """ToTResult creation."""
        result = ToTResult(
            answer="Solution",
            best_path=["step1", "step2"]
        )
        assert result.answer == "Solution"
        assert len(result.best_path) == 2
        assert result.total_nodes_explored == 0

    def test_with_stats(self):
        """ToTResult with statistics."""
        result = ToTResult(
            answer="Answer",
            best_path=["a", "b"],
            total_nodes_explored=15,
            max_depth_reached=5,
            branches_explored=3
        )
        assert result.total_nodes_explored == 15
        assert result.max_depth_reached == 5


class TestTreeOfThought:
    """Test cases for TreeOfThought class."""

    def test_init_default(self):
        """Default initialization."""
        tot = TreeOfThought()
        assert tot.max_depth == 4
        assert tot.branch_factor == 3

    def test_init_custom(self):
        """Custom parameters."""
        tot = TreeOfThought(max_depth=6, branch_factor=5, beam_width=2)
        assert tot.max_depth == 6
        assert tot.branch_factor == 5
        assert tot.beam_width == 2

    def test_default_evaluation_threshold(self):
        """Default evaluation threshold."""
        tot = TreeOfThought()
        assert tot.evaluation_threshold == 5.0