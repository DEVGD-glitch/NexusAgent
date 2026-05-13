"""
Tests for nexus.reasoning.lats - LATS (Language Agent Tree Search).
"""

import pytest
from nexus.reasoning.lats import (
    MCTSNode,
    LATSResult,
    LATSReasoner,
)


class TestMCTSNode:
    """Test cases for MCTSNode dataclass."""

    def test_creation_defaults(self):
        """MCTSNode with defaults."""
        node = MCTSNode(state="State 1", action="Action 1")
        assert node.state == "State 1"
        assert node.action == "Action 1"
        assert node.parent is None
        assert node.children == []
        assert node.visits == 0
        assert node.value == 0.0

    def test_q_value_zero_visits(self):
        """Q-value is 0 when no visits."""
        node = MCTSNode(state="Test", action="Test")
        assert node.q_value == 0.0

    def test_q_value_with_visits(self):
        """Q-value calculation."""
        node = MCTSNode(state="Test", action="Test", visits=5, value=15.0)
        assert node.q_value == 3.0

    def test_ucb1_no_visits(self):
        """UCB1 returns inf when no visits."""
        node = MCTSNode(state="Test", action="Test")
        ucb = node.ucb1()
        assert ucb == float("inf")

    def test_ucb1_with_visits(self):
        """UCB1 calculation with visits."""
        parent = MCTSNode(state="Parent", action="Parent", visits=10)
        node = MCTSNode(state="Test", action="Test", parent=parent, visits=5, value=10.0)
        ucb = node.ucb1()
        assert ucb > 0

    def test_to_dict(self):
        """Convert to dict."""
        node = MCTSNode(state="State", action="Action", visits=3, value=6.0, depth=2)
        d = node.to_dict()
        assert "q_value" in d
        assert d["q_value"] == 2.0
        assert "visits" in d
        assert d["depth"] == 2


class TestLATSResult:
    """Test cases for LATSResult dataclass."""

    def test_creation(self):
        """LATSResult creation."""
        result = LATSResult(answer="Solution", best_path=["step1", "step2"])
        assert result.answer == "Solution"
        assert len(result.best_path) == 2


class TestLATSReasoner:
    """Test cases for LATSReasoner class."""

    def test_init_defaults(self):
        """Default initialization."""
        reasoner = LATSReasoner()
        assert reasoner.max_simulations == 20
        assert reasoner.exploration_weight == 1.414

    def test_init_custom(self):
        """Custom parameters."""
        reasoner = LATSReasoner(max_simulations=50, exploration_weight=2.0)
        assert reasoner.max_simulations == 50
        assert reasoner.exploration_weight == 2.0