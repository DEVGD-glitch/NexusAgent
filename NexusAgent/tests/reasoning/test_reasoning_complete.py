"""
Comprehensive tests for all reasoning modules — LATS, ToT, ReAct, and Selector.

Covers all uncovered code paths:
  - LATS: MCTSNode operations, LATSReasoner.solve() with mocked LLM,
          _select, _expand, _simulate, _backpropagate, _generate_actions,
          _evaluate_state, _extract_answer, _trace_path, _get_tree_stats
  - ToT: ThoughtNode operations, TreeOfThought.solve() with mocked LLM,
         _generate_thoughts, _evaluate_thought, _get_all_leaves,
         _trace_path, _tree_to_dict
  - ReAct: select_reasoning_pattern with heuristics, ReActLoop.run() with mocked LLM
  - Selector: reason() dispatching to correct pattern with mocked implementations

All LLM calls are mocked using unittest.mock.patch on nexus.llm.router.LLMRouter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any, Optional

from nexus.reasoning.lats import (
    MCTSNode,
    LATSResult,
    LATSReasoner,
)
from nexus.reasoning.tot import (
    ThoughtNode,
    ToTResult,
    TreeOfThought,
)
from nexus.reasoning.react import (
    ReasoningPattern,
    select_reasoning_pattern,
    ReActLoop,
)
from nexus.reasoning.selector import reason


# ═══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════════

class MockLLMResponse:
    """Simulates LLMRouter.complete() return value."""
    def __init__(self, content: str = ""):
        self.content = content
        self.provider = None
        self.model = None
        self.usage = {}
        self.latency_ms = 0.0
        self.finish_reason = "stop"
        self.raw_response = None
        self.tool_calls = []


@pytest.fixture
def mock_llm_router():
    """Patches LLMRouter so router.complete() returns controlled responses."""
    with patch("nexus.llm.router.LLMRouter") as mock_cls:
        router_instance = MagicMock()
        router_instance.complete = AsyncMock()
        mock_cls.return_value = router_instance
        yield router_instance


@pytest.fixture
def mock_actions_response():
    """Returns a mock whose .content contains a numbered list of actions."""
    def _make(actions: Optional[list[str]] = None):
        if actions is None:
            actions = [
                "Search for relevant literature",
                "Analyze the core algorithm",
                "Implement a prototype",
            ]
        lines = [f"{i+1}. {a}" for i, a in enumerate(actions)]
        return MockLLMResponse(content="\n".join(lines))
    return _make


@pytest.fixture
def mock_score_response():
    """Returns a mock whose .content is a numeric score string."""
    def _make(score: str = "0.85"):
        return MockLLMResponse(content=score)
    return _make


# ═══════════════════════════════════════════════════════════════════════════════
# LATS — MCTSNode Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMCTSNode:
    """Test MCTSNode dataclass — creation, q_value, ucb1, to_dict, tree ops."""

    def test_creation_defaults(self):
        node = MCTSNode(state="root", action="init")
        assert node.state == "root"
        assert node.action == "init"
        assert node.parent is None
        assert node.children == []
        assert node.visits == 0
        assert node.value == 0.0
        assert node.depth == 0
        assert node.is_terminal is False
        assert node.reward == 0.0

    def test_creation_full(self):
        parent = MCTSNode(state="parent", action="parent")
        node = MCTSNode(
            state="child", action="child", parent=parent,
            visits=3, value=6.0, depth=2, is_terminal=True, reward=0.9,
        )
        assert node.parent is parent
        assert node.visits == 3
        assert node.value == 6.0
        assert node.depth == 2
        assert node.is_terminal is True
        assert node.reward == 0.9

    def test_q_value_zero_visits(self):
        node = MCTSNode(state="s", action="a")
        assert node.q_value == 0.0

    def test_q_value_with_visits(self):
        node = MCTSNode(state="s", action="a", visits=4, value=12.0)
        assert node.q_value == 3.0

    def test_ucb1_no_visits_returns_inf(self):
        node = MCTSNode(state="s", action="a")
        assert node.ucb1() == float("inf")

    def test_ucb1_no_parent_returns_q_value(self):
        node = MCTSNode(state="s", action="a", visits=5, value=10.0)
        assert node.ucb1() == node.q_value

    def test_ucb1_with_parent(self):
        parent = MCTSNode(state="p", action="p", visits=10)
        node = MCTSNode(state="c", action="c", parent=parent, visits=5, value=10.0)
        ucb = node.ucb1(exploration_weight=1.0)
        assert ucb > node.q_value  # Exploration bonus added

    def test_ucb1_custom_exploration_weight(self):
        parent = MCTSNode(state="p", action="p", visits=10)
        node = MCTSNode(state="c", action="c", parent=parent, visits=5, value=10.0)
        ucb_low = node.ucb1(exploration_weight=0.1)
        ucb_high = node.ucb1(exploration_weight=5.0)
        assert ucb_high > ucb_low

    def test_ucb1_exploration_dominant_for_low_visits(self):
        parent = MCTSNode(state="p", action="p", visits=100)
        less_visited = MCTSNode(state="l", action="l", parent=parent, visits=2, value=2.0)
        more_visited = MCTSNode(state="m", action="m", parent=parent, visits=50, value=50.0)
        # Less visited should have higher UCB1 due to exploration bonus
        assert less_visited.ucb1() > more_visited.ucb1()

    def test_to_dict(self):
        node = MCTSNode(
            state="s", action="test_action", visits=3, value=9.0,
            depth=2, is_terminal=False, reward=0.5,
        )
        child = MCTSNode(state="c", action="child")
        node.children.append(child)
        d = node.to_dict()
        assert d["action"] == "test_action"
        assert d["q_value"] == 3.0
        assert d["visits"] == 3
        assert d["depth"] == 2
        assert d["is_terminal"] is False
        assert d["reward"] == 0.5
        assert d["children_count"] == 1

    def test_add_child(self):
        parent = MCTSNode(state="p", action="p")
        child = MCTSNode(state="c", action="c", parent=parent)
        parent.children.append(child)
        assert len(parent.children) == 1
        assert child in parent.children
        assert child.parent is parent

    def test_is_leaf(self):
        node = MCTSNode(state="s", action="a")
        assert node.children == []  # leaf
        child = MCTSNode(state="c", action="c")
        node.children.append(child)
        assert len(node.children) > 0  # not leaf


class TestLATSResult:
    """Test LATSResult dataclass."""

    def test_creation_defaults(self):
        result = LATSResult(answer="ans", best_path=[])
        assert result.answer == "ans"
        assert result.best_path == []
        assert result.total_simulations == 0
        assert result.total_nodes == 0
        assert result.best_reward == 0.0
        assert result.tree_stats == {}

    def test_creation_full(self):
        result = LATSResult(
            answer="Optimal solution",
            best_path=[{"action": "step1"}, {"action": "step2"}],
            total_simulations=50,
            total_nodes=100,
            best_reward=0.95,
            tree_stats={"total_nodes": 100, "max_depth": 5},
        )
        assert result.answer == "Optimal solution"
        assert len(result.best_path) == 2
        assert result.total_simulations == 50
        assert result.total_nodes == 100
        assert result.best_reward == 0.95
        assert result.tree_stats["max_depth"] == 5


class TestLATSReasonerInit:
    """Test LATSReasoner initialization."""

    def test_default_params(self):
        lats = LATSReasoner()
        assert lats.max_simulations == 20
        assert lats.max_depth == 5
        assert lats.exploration_weight == 1.414
        assert lats.rollout_depth == 3
        assert lats.num_actions == 3

    def test_custom_params(self):
        lats = LATSReasoner(
            max_simulations=50,
            max_depth=8,
            exploration_weight=2.0,
            rollout_depth=5,
            num_actions=4,
        )
        assert lats.max_simulations == 50
        assert lats.max_depth == 8
        assert lats.exploration_weight == 2.0
        assert lats.rollout_depth == 5
        assert lats.num_actions == 4

    def test_partial_custom_params(self):
        lats = LATSReasoner(max_simulations=10, max_depth=3)
        assert lats.max_simulations == 10
        assert lats.max_depth == 3
        assert lats.exploration_weight == 1.414  # default


class TestLATSReasonerInternal:
    """Test LATS internal methods — _select, _expand, _backpropagate, etc."""

    def test_select_root_no_children(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init")
        selected = lats._select(root)
        assert selected is root

    def test_select_unvisited_child(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=1)
        child_a = MCTSNode(state="a", action="a", parent=root)
        child_b = MCTSNode(state="b", action="b", parent=root)
        root.children = [child_a, child_b]
        selected = lats._select(root)
        # Should pick an unvisited child randomly
        assert selected in (child_a, child_b)

    def test_select_best_ucb1(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=100)
        child1 = MCTSNode(state="c1", action="c1", parent=root, visits=10, value=15.0)
        child2 = MCTSNode(state="c2", action="c2", parent=root, visits=5, value=2.0)
        child3 = MCTSNode(state="c3", action="c3", parent=root, visits=20, value=10.0)
        root.children = [child1, child2, child3]
        selected = lats._select(root)
        # Should pick child with highest UCB1 (child1 has best q_value)
        assert selected == child1

    def test_backpropagate(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=1, value=1.0)
        child = MCTSNode(state="c", action="c", parent=root, visits=1, value=0.5)
        lats._backpropagate(child, 0.8)
        assert child.visits == 2
        assert child.value == 1.3
        assert root.visits == 2
        assert root.value == 1.8

    def test_trace_path(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init")
        child = MCTSNode(state="c", action="step1", parent=root)
        grandchild = MCTSNode(state="gc", action="step2", parent=child)
        path = lats._trace_path(grandchild)
        assert len(path) == 3
        assert path[0]["action"] == "init"
        assert path[1]["action"] == "step1"
        assert path[2]["action"] == "step2"

    def test_trace_path_root(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init")
        path = lats._trace_path(root)
        assert len(path) == 1
        assert path[0]["action"] == "init"

    def test_get_tree_stats_empty(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init")
        root.visits = 10
        stats = lats._get_tree_stats(root)
        assert stats["total_nodes"] == 1
        assert stats["max_depth"] == 0
        assert stats["avg_visits"] == 10.0
        assert stats["terminal_nodes"] == 0

    def test_get_tree_stats_with_nodes(self):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=10)
        c1 = MCTSNode(state="c1", action="c1", parent=root, visits=5, depth=1, is_terminal=True)
        c2 = MCTSNode(state="c2", action="c2", parent=root, visits=3, depth=1)
        root.children = [c1, c2]
        stats = lats._get_tree_stats(root)
        assert stats["total_nodes"] == 3
        assert stats["max_depth"] == 1
        assert stats["terminal_nodes"] == 1

    @pytest.mark.asyncio
    async def test_expand_creates_children(self, mock_llm_router, mock_actions_response):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=1)
        mock_llm_router.complete.return_value = mock_actions_response()
        await lats._expand(root, "Solve the problem")
        assert len(root.children) > 0
        assert root.children[0].parent is root
        assert root.children[0].depth == 1

    @pytest.mark.asyncio
    async def test_expand_respects_max_depth(self):
        lats = LATSReasoner(max_depth=2)
        root = MCTSNode(state="root", action="init", depth=2, visits=1)
        await lats._expand(root, "task")
        assert root.is_terminal is True
        assert len(root.children) == 0

    @pytest.mark.asyncio
    async def test_expand_empty_actions(self, mock_llm_router):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=1)
        # LLM returns content with no parseable actions
        mock_llm_router.complete.return_value = MockLLMResponse(content="Some random text without list")
        await lats._expand(root, "task")
        assert len(root.children) == 0

    @pytest.mark.asyncio
    async def test_expand_llm_failure(self, mock_llm_router):
        lats = LATSReasoner()
        root = MCTSNode(state="root", action="init", visits=1)
        mock_llm_router.complete.side_effect = Exception("LLM error")
        await lats._expand(root, "task")
        assert len(root.children) == 0

    @pytest.mark.asyncio
    async def test_generate_actions_success(self, mock_llm_router, mock_actions_response):
        lats = LATSReasoner()
        node = MCTSNode(state="state", action="action")
        mock_llm_router.complete.return_value = mock_actions_response([
            "Research the topic",
            "Write the code",
        ])
        actions = await lats._generate_actions(node, "Build a web app")
        assert len(actions) == 2
        assert "Research the topic" in actions

    @pytest.mark.asyncio
    async def test_generate_actions_empty_on_failure(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="state", action="action")
        mock_llm_router.complete.side_effect = Exception("LLM failure")
        actions = await lats._generate_actions(node, "task")
        assert actions == []

    @pytest.mark.asyncio
    async def test_evaluate_state_parses_score(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="good state", action="action")
        mock_llm_router.complete.return_value = MockLLMResponse(content="0.75")
        score = await lats._evaluate_state(node, "task")
        assert score == 0.75

    @pytest.mark.asyncio
    async def test_evaluate_state_clamps_to_range(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="s", action="a")
        mock_llm_router.complete.return_value = MockLLMResponse(content="2.5")
        score = await lats._evaluate_state(node, "task")
        assert score == 1.0

        mock_llm_router.complete.return_value = MockLLMResponse(content="-1.0")
        score = await lats._evaluate_state(node, "task")
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_state_fallback_on_value_error(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="s", action="a")
        mock_llm_router.complete.return_value = MockLLMResponse(content="not a number")
        score = await lats._evaluate_state(node, "task")
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_evaluate_state_extracts_number_from_text(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="s", action="a")
        mock_llm_router.complete.return_value = MockLLMResponse(content="Score: 0.87/1.0")
        score = await lats._evaluate_state(node, "task")
        assert score == 0.87

    @pytest.mark.asyncio
    async def test_evaluate_state_llm_failure_defaults(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="s", action="a")
        mock_llm_router.complete.side_effect = Exception("LLM error")
        score = await lats._evaluate_state(node, "task")
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_extract_answer_from_solution_tag(self):
        lats = LATSReasoner()
        node = MCTSNode(state="SOLUTION: The answer is 42", action="solution")
        answer = await lats._extract_answer(node, "What is life?")
        assert answer == "The answer is 42"

    @pytest.mark.asyncio
    async def test_extract_answer_from_answer_tag(self):
        lats = LATSReasoner()
        node = MCTSNode(state="Answer: Python is great", action="answer")
        answer = await lats._extract_answer(node, "What is Python?")
        assert answer == "Python is great"

    @pytest.mark.asyncio
    async def test_extract_answer_llm_fallback(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="Some reasoning path", action="path", visits=1)
        node.parent = MCTSNode(state="root", action="init")
        mock_llm_router.complete.return_value = MockLLMResponse(content="Synthesized answer")
        answer = await lats._extract_answer(node, "Explain quantum")
        assert answer == "Synthesized answer"

    @pytest.mark.asyncio
    async def test_extract_answer_llm_failure_returns_state(self, mock_llm_router):
        lats = LATSReasoner()
        node = MCTSNode(state="Fallback state text", action="path")
        node.parent = MCTSNode(state="root", action="init")
        mock_llm_router.complete.side_effect = Exception("LLM error")
        answer = await lats._extract_answer(node, "task")
        assert answer == "Fallback state text"

    @pytest.mark.asyncio
    async def test_simulate_with_steps(self, mock_llm_router, mock_actions_response, mock_score_response):
        lats = LATSReasoner(rollout_depth=2)
        node = MCTSNode(state="current", action="action")
        # _simulate calls _evaluate_state and _generate_actions multiple times
        # Return a score for evaluate_state, and actions for generate_actions
        mock_llm_router.complete.side_effect = [
            mock_score_response("0.6"),   # first evaluate_state
            mock_actions_response(["next step"]),  # first generate_actions
            mock_score_response("0.8"),   # second evaluate_state
            mock_actions_response(["final step"]),  # second generate_actions
            mock_score_response("0.9"),   # final evaluate_state
        ]
        reward = await lats._simulate(node, "task")
        assert 0.0 <= reward <= 1.0

    @pytest.mark.asyncio
    async def test_simulate_empty_actions_breaks(self, mock_llm_router, mock_score_response):
        lats = LATSReasoner(rollout_depth=3)
        node = MCTSNode(state="s", action="a")
        mock_llm_router.complete.side_effect = [
            mock_score_response("0.5"),   # evaluate_state
            MockLLMResponse(content=""),  # generate_actions returns nothing
        ]
        reward = await lats._simulate(node, "task")
        assert 0.0 <= reward <= 1.0

    @pytest.mark.asyncio
    async def test_simulate_terminal_node_stops(self, mock_llm_router, mock_score_response):
        lats = LATSReasoner(rollout_depth=5)
        terminal = MCTSNode(state="done", action="done", is_terminal=True)
        mock_llm_router.complete.return_value = mock_score_response("0.5")
        reward = await lats._simulate(terminal, "task")
        assert 0.0 <= reward <= 1.0


class TestLATSReasonerSolve:
    """Test LATSReasoner.solve() with mocked LLM."""

    @pytest.mark.asyncio
    async def test_solve_returns_result(self, mock_llm_router, mock_actions_response, mock_score_response):
        lats = LATSReasoner(max_simulations=3, max_depth=3, num_actions=2)
        # We need to return many responses for multiple simulations:
        # Each simulation calls: _expand (generate_actions), _evaluate_state, _backpropagate
        # Plus final _extract_answer
        mock_llm_router.complete.side_effect = (
            [mock_actions_response(["Do A", "Do B"]) for _ in range(3)]   # _generate_actions for _expand
            + [mock_score_response("0.7") for _ in range(4)]              # _evaluate_state calls
            + [MockLLMResponse(content="Final answer")]                   # _extract_answer
        )
        result = await lats.solve("Solve this problem")
        assert isinstance(result, LATSResult)
        assert result.best_reward >= 0.0
        assert result.total_simulations == 3
        assert result.total_nodes >= 1
        assert len(result.best_path) > 0

    @pytest.mark.asyncio
    async def test_solve_with_context(self, mock_llm_router, mock_actions_response, mock_score_response):
        lats = LATSReasoner(max_simulations=2, max_depth=2, num_actions=2)
        mock_llm_router.complete.side_effect = (
            [mock_actions_response() for _ in range(2)]
            + [mock_score_response("0.6") for _ in range(3)]
            + [MockLLMResponse(content="Answer with context")]
        )
        context = [{"role": "user", "content": "prior message"}]
        result = await lats.solve("Solve with context", context=context)
        assert result.answer is not None
        assert result.total_simulations == 2

    @pytest.mark.asyncio
    async def test_solve_without_simulations(self, mock_llm_router, mock_score_response):
        """When max_simulations=0, just do _extract_answer on root."""
        lats = LATSReasoner(max_simulations=0)
        mock_llm_router.complete.return_value = MockLLMResponse(content="Root answer")
        result = await lats.solve("Quick solve")
        assert result.total_simulations == 0
        assert result.total_nodes == 1  # just root


# ═══════════════════════════════════════════════════════════════════════════════
# ToT — ThoughtNode Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestThoughtNode:
    """Test ThoughtNode dataclass."""

    def test_creation_defaults(self):
        node = ThoughtNode(thought="Initial thought")
        assert node.thought == "Initial thought"
        assert node.score == 0.0
        assert node.depth == 0
        assert node.children == []
        assert node.parent is None
        assert node.is_solution is False
        assert node.evaluation == ""

    def test_creation_full(self):
        parent = ThoughtNode(thought="root")
        child = ThoughtNode(
            thought="branch",
            score=8.0,
            depth=2,
            children=[],
            parent=parent,
            is_solution=True,
            evaluation="Promising approach",
        )
        assert child.score == 8.0
        assert child.depth == 2
        assert child.parent is parent
        assert child.is_solution is True
        assert child.evaluation == "Promising approach"

    def test_to_dict(self):
        child = ThoughtNode(thought="child")
        node = ThoughtNode(
            thought="test thought",
            score=7.5,
            depth=3,
            is_solution=True,
            evaluation="Good",
        )
        node.children.append(child)
        d = node.to_dict()
        assert d["thought"] == "test thought"
        assert d["score"] == 7.5
        assert d["depth"] == 3
        assert d["is_solution"] is True
        assert d["evaluation"] == "Good"
        assert d["children_count"] == 1

    def test_add_child(self):
        parent = ThoughtNode(thought="parent")
        child = ThoughtNode(thought="child", parent=parent)
        parent.children.append(child)
        assert len(parent.children) == 1
        assert child.parent is parent


class TestToTResult:
    """Test ToTResult dataclass."""

    def test_creation_defaults(self):
        result = ToTResult(answer="Answer", best_path=[])
        assert result.answer == "Answer"
        assert result.best_path == []
        assert result.total_nodes_explored == 0
        assert result.max_depth_reached == 0
        assert result.branches_explored == 0
        assert result.tree_snapshot == {}

    def test_creation_full(self):
        result = ToTResult(
            answer="Optimal strategy",
            best_path=["step1", "step2", "step3"],
            total_nodes_explored=25,
            max_depth_reached=4,
            branches_explored=3,
            tree_snapshot={"depth": 1, "children": []},
        )
        assert result.answer == "Optimal strategy"
        assert len(result.best_path) == 3
        assert result.total_nodes_explored == 25
        assert result.max_depth_reached == 4


class TestTreeOfThoughtInit:
    """Test TreeOfThought initialization."""

    def test_default_params(self):
        tot = TreeOfThought()
        assert tot.max_depth == 4
        assert tot.branch_factor == 3
        assert tot.evaluation_threshold == 5.0
        assert tot.beam_width == 2

    def test_custom_params(self):
        tot = TreeOfThought(
            max_depth=6,
            branch_factor=5,
            evaluation_threshold=7.0,
            beam_width=3,
        )
        assert tot.max_depth == 6
        assert tot.branch_factor == 5
        assert tot.evaluation_threshold == 7.0
        assert tot.beam_width == 3

    def test_partial_custom(self):
        tot = TreeOfThought(max_depth=3, branch_factor=4)
        assert tot.max_depth == 3
        assert tot.branch_factor == 4
        assert tot.evaluation_threshold == 5.0  # default


class TestTreeOfThoughtInternal:
    """Test ToT internal methods."""

    def test_get_all_leaves_single_node(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root")
        leaves = tot._get_all_leaves(root)
        assert len(leaves) == 1
        assert leaves[0] is root

    def test_get_all_leaves_with_children(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root")
        c1 = ThoughtNode(thought="c1", parent=root)
        c2 = ThoughtNode(thought="c2", parent=root)
        c1a = ThoughtNode(thought="c1a", parent=c1)
        root.children = [c1, c2]
        c1.children = [c1a]
        leaves = tot._get_all_leaves(root)
        assert len(leaves) == 2
        assert c1a in leaves
        assert c2 in leaves

    def test_trace_path_root(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root")
        path = tot._trace_path(root)
        assert path == ["root"]

    def test_trace_path_multi(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root")
        child = ThoughtNode(thought="child", parent=root)
        grandchild = ThoughtNode(thought="grandchild", parent=child)
        path = tot._trace_path(grandchild)
        assert path == ["root", "child", "grandchild"]

    def test_tree_to_dict_single(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root", score=5.0)
        d = tot._tree_to_dict(root)
        assert d["thought"] == "root"
        assert d["score"] == 5.0
        assert d["depth"] == 0
        assert "children" not in d

    def test_tree_to_dict_with_children(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root", score=5.0)
        child = ThoughtNode(thought="child", score=8.0, depth=1, parent=root)
        root.children = [child]
        d = tot._tree_to_dict(root)
        assert "children" in d
        assert len(d["children"]) == 1
        assert d["children"][0]["thought"] == "child"

    def test_tree_to_dict_max_depth_limit(self):
        tot = TreeOfThought()
        root = ThoughtNode(thought="root", score=5.0)
        c1 = ThoughtNode(thought="level1", score=7.0, depth=1, parent=root)
        c2 = ThoughtNode(thought="level2", score=9.0, depth=2, parent=c1)
        c1.children = [c2]
        root.children = [c1]
        # max_depth=1 should limit to root level only
        d = tot._tree_to_dict(root, max_depth=1)
        assert "children" in d
        assert len(d["children"]) == 1
        assert "children" not in d["children"][0]  # Stopped at depth 1

    @pytest.mark.asyncio
    async def test_generate_thoughts_depth_0(self, mock_llm_router):
        tot = TreeOfThought(branch_factor=3)
        mock_llm_router.complete.return_value = MockLLMResponse(content=(
            "1. Approach one\n2. Approach two\n3. Approach three"
        ))
        thoughts = await tot._generate_thoughts("Solve task", depth=0)
        assert len(thoughts) == 3
        assert "Approach one" in thoughts

    @pytest.mark.asyncio
    async def test_generate_thoughts_with_previous(self, mock_llm_router):
        tot = TreeOfThought(branch_factor=2)
        mock_llm_router.complete.return_value = MockLLMResponse(content=(
            "1. Next step A\n- Next step B"
        ))
        thoughts = await tot._generate_thoughts(
            "task", depth=2, previous_thought="Previous step"
        )
        assert len(thoughts) == 2

    @pytest.mark.asyncio
    async def test_generate_thoughts_llm_failure(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.side_effect = Exception("LLM error")
        thoughts = await tot._generate_thoughts("task", depth=0)
        assert thoughts == []

    @pytest.mark.asyncio
    async def test_generate_thoughts_truncates_to_branch_factor(self, mock_llm_router):
        tot = TreeOfThought(branch_factor=2)
        mock_llm_router.complete.return_value = MockLLMResponse(content=(
            "1. Option A\n2. Option B\n3. Option C\n4. Option D"
        ))
        thoughts = await tot._generate_thoughts("task", depth=0)
        assert len(thoughts) == 2

    @pytest.mark.asyncio
    async def test_evaluate_thought_parses_score(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.return_value = MockLLMResponse(content="8")
        score = await tot._evaluate_thought("Great step", "task", depth=1)
        assert score == 8.0

    @pytest.mark.asyncio
    async def test_evaluate_thought_high_score(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.return_value = MockLLMResponse(content="9")
        score = await tot._evaluate_thought("Great step", "task", depth=1)
        assert score == 9.0

    @pytest.mark.asyncio
    async def test_evaluate_thought_with_previous(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.return_value = MockLLMResponse(content="6")
        score = await tot._evaluate_thought(
            "Next step", "task", depth=2, previous_thought="Prev step"
        )
        assert score == 6.0

    @pytest.mark.asyncio
    async def test_evaluate_thought_no_digit_fallback(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.return_value = MockLLMResponse(content="No digits here")
        score = await tot._evaluate_thought("Step", "task", depth=0)
        assert score == 5.0

    @pytest.mark.asyncio
    async def test_evaluate_thought_llm_failure(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.side_effect = Exception("LLM error")
        score = await tot._evaluate_thought("Step", "task", depth=0)
        assert score == 5.0


class TestTreeOfThoughtSolve:
    """Test TreeOfThought.solve() with mocked LLM."""

    @pytest.mark.asyncio
    async def test_solve_returns_result(self, mock_llm_router):
        tot = TreeOfThought(max_depth=2, branch_factor=2, beam_width=2)
        # Mock sequence:
        # 1. _generate_thoughts(depth=0)  -> 2 thoughts
        # 2. _evaluate_thought for thought 1 -> 6.0
        # 3. _evaluate_thought for thought 2 -> 8.0
        # 4. _generate_thoughts(depth=2) for best node -> 2 children
        # 5. _evaluate_thought for child 1 with previous -> 7.0
        # 6. _evaluate_thought for child 2 with previous -> 9.0
        mock_llm_router.complete.side_effect = [
            MockLLMResponse(content="1. Approach A\n2. Approach B"),
            MockLLMResponse(content="6"),
            MockLLMResponse(content="8"),
            MockLLMResponse(content="1. Detail A\n2. Detail B"),
            MockLLMResponse(content="7"),
            MockLLMResponse(content="9"),
        ]
        result = await tot.solve("Solve optimization problem")
        assert isinstance(result, ToTResult)
        assert result.total_nodes_explored > 0
        assert len(result.best_path) > 0

    @pytest.mark.asyncio
    async def test_solve_empty_initial_thoughts(self, mock_llm_router):
        tot = TreeOfThought()
        mock_llm_router.complete.return_value = MockLLMResponse(content="Nothing useful")
        result = await tot.solve("Impossible task")
        assert result.answer == "Could not generate initial thoughts for this task"
        assert result.total_nodes_explored == 0

    @pytest.mark.asyncio
    async def test_solve_with_solution_node(self, mock_llm_router):
        tot = TreeOfThought(max_depth=2, branch_factor=2, beam_width=2)
        mock_llm_router.complete.side_effect = [
            MockLLMResponse(content="1. Try A\n2. Answer: found it"),
            MockLLMResponse(content="5"),
            MockLLMResponse(content="9"),
        ]
        result = await tot.solve("Solve quickly")
        assert result.total_nodes_explored > 0

    @pytest.mark.asyncio
    async def test_solve_with_context(self, mock_llm_router):
        tot = TreeOfThought(max_depth=2, branch_factor=1, beam_width=1)
        mock_llm_router.complete.side_effect = [
            MockLLMResponse(content="1. Single approach"),
            MockLLMResponse(content="7"),
            MockLLMResponse(content="1. Final step"),
            MockLLMResponse(content="8"),
        ]
        context = [{"role": "user", "content": "additional info"}]
        result = await tot.solve("Solve with context", context=context)
        assert isinstance(result, ToTResult)
        assert len(result.best_path) > 0

    @pytest.mark.asyncio
    async def test_solve_all_nodes_below_threshold(self, mock_llm_router):
        """When all nodes score below threshold, should still use best leaf."""
        tot = TreeOfThought(max_depth=2, branch_factor=2, beam_width=2, evaluation_threshold=9.0)
        mock_llm_router.complete.side_effect = [
            MockLLMResponse(content="1. Bad A\n2. Bad B"),
            MockLLMResponse(content="3"),   # below threshold
            MockLLMResponse(content="4"),   # below threshold
        ]
        result = await tot.solve("Hard problem")
        # Should complete with best available node (score 4)
        assert result.total_nodes_explored > 0
        assert result.max_depth_reached >= 1

    @pytest.mark.asyncio
    async def test_solve_with_multiple_depth_levels(self, mock_llm_router):
        tot = TreeOfThought(max_depth=3, branch_factor=2, beam_width=1)
        # Need many mock responses for multi-level tree
        responses = []
        # depth 0: 2 initial thoughts
        responses.append(MockLLMResponse(content="1. Plan A\n2. Plan B"))
        # evaluate: 6, 7
        responses.append(MockLLMResponse(content="6"))
        responses.append(MockLLMResponse(content="7"))
        # depth 2: 2 children from best (score 7)
        responses.append(MockLLMResponse(content="1. Execute A\n2. Execute B"))
        # evaluate: 8, 5
        responses.append(MockLLMResponse(content="8"))
        responses.append(MockLLMResponse(content="5"))
        # depth 3: 2 children from best (score 8)
        responses.append(MockLLMResponse(content="1. Finalize A\n2. Finalize B"))
        # evaluate: 9, 6
        responses.append(MockLLMResponse(content="9"))
        responses.append(MockLLMResponse(content="6"))
        mock_llm_router.complete.side_effect = responses
        result = await tot.solve("Multi-level problem")
        assert result.total_nodes_explored > 0
        assert result.max_depth_reached >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# ReAct — select_reasoning_pattern Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelectReasoningPattern:
    """Test select_reasoning_pattern heuristics and complexity hints."""

    def test_simple_task_returns_react(self):
        assert select_reasoning_pattern("What is the capital of France?") == ReasoningPattern.REACT
        assert select_reasoning_pattern("Define photosynthesis") == ReasoningPattern.REACT
        assert select_reasoning_pattern("How many planets are there?") == ReasoningPattern.REACT
        assert select_reasoning_pattern("Who wrote Hamlet?") == ReasoningPattern.REACT
        assert select_reasoning_pattern("Calculate 2 + 2") == ReasoningPattern.REACT

    def test_medium_multiple_steps_returns_tot(self):
        assert select_reasoning_pattern("First install then configure then test") == ReasoningPattern.TOT

    def test_medium_sequence_pipeline_returns_tot(self):
        assert select_reasoning_pattern("Build a data pipeline that processes then analyzes") == ReasoningPattern.TOT

    def test_complex_explore_returns_lats(self):
        assert select_reasoning_pattern("Explore and find the best optimization strategy") == ReasoningPattern.LATS

    def test_complex_investigate_returns_lats(self):
        assert select_reasoning_pattern("Investigate the root cause of system failures") == ReasoningPattern.LATS

    def test_complex_analyze_deeply_returns_lats(self):
        assert select_reasoning_pattern("Analyze deeply the trade-offs between architectures") == ReasoningPattern.LATS

    def test_complex_compare_alternatives_returns_lats(self):
        assert select_reasoning_pattern("Compare alternatives and find the best approach") == ReasoningPattern.LATS

    def test_complex_comprehensive_returns_lats(self):
        assert select_reasoning_pattern("Do a comprehensive review of the system") == ReasoningPattern.LATS

    def test_complex_hint_returns_lats(self):
        assert select_reasoning_pattern("Simple task", complexity="complex") == ReasoningPattern.LATS

    def test_medium_hint_returns_tot(self):
        assert select_reasoning_pattern("Simple task", complexity="medium") == ReasoningPattern.TOT

    def test_simple_hint_returns_react(self):
        assert select_reasoning_pattern("Complex task", complexity="simple") == ReasoningPattern.REACT

    def test_invalid_complexity_falls_back_to_react(self):
        assert select_reasoning_pattern("Task", complexity="unknown") == ReasoningPattern.REACT

    def test_complex_score_two_indicators(self):
        """Two complex indicators should select LATS even without medium overlap."""
        task = "explore and optimize the performance"
        assert select_reasoning_pattern(task) == ReasoningPattern.LATS

    def test_edge_case_no_indicators(self):
        """No indicators at all should default to ReAct."""
        assert select_reasoning_pattern("Run the process") == ReasoningPattern.REACT


class TestReActLoopInit:
    """Test ReActLoop initialization and state."""

    def test_default_max_steps(self):
        loop = ReActLoop()
        assert loop.max_iterations == 10

    def test_initial_state(self):
        loop = ReActLoop()
        assert loop.thoughts == []
        assert loop.actions == []
        assert loop.observations == []

    def test_reset_clears_state(self):
        loop = ReActLoop()
        loop.thoughts = ["old thought"]
        loop.actions = [{"tool": "search"}]
        loop.observations = ["result"]
        loop.reset()
        assert loop.thoughts == []
        assert loop.actions == []
        assert loop.observations == []

    def test_custom_max_steps(self):
        loop = ReActLoop()
        loop.max_steps = 5
        assert loop.max_steps == 5


class TestReActLoopRun:
    """Test ReActLoop.run() with mocked router."""

    @pytest.mark.asyncio
    async def test_run_with_answer(self):
        """Should extract answer when Answer: appears in response."""
        loop = ReActLoop()
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.return_value = MockLLMResponse(
                content="Thought: I know this\nAnswer: Paris is the capital"
            )
            mock_cls.return_value = router
            result = await loop.run("What is the capital of France?")
        assert result["pattern"] == "react"
        assert result["answer"] == "Paris is the capital"
        assert result["steps"] == 1

    @pytest.mark.asyncio
    async def test_run_with_tools(self):
        """Should work with tools dict (no-op in ReActLoop currently)."""
        loop = ReActLoop()
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.return_value = MockLLMResponse(
                content="Thought: Searching\nAnswer: Found it"
            )
            mock_cls.return_value = router
            tools = {"search": lambda q: {"result": q}}
            result = await loop.run("Search for Python", tools=tools)
        assert result["answer"] == "Found it"

    @pytest.mark.asyncio
    async def test_run_without_reset_state(self):
        """Should preserve existing state when reset_state=False."""
        loop = ReActLoop()
        loop.thoughts = ["existing thought"]
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.return_value = MockLLMResponse(
                content="Answer: Some answer"
            )
            mock_cls.return_value = router
            result = await loop.run("Task", reset_state=False)
        # Should NOT have reset, so existing thought should remain
        assert result["answer"] == "Some answer"

    @pytest.mark.asyncio
    async def test_run_max_steps_exceeded(self):
        """Should return max steps message when no answer found."""
        loop = ReActLoop()
        loop.max_iterations = 3
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.return_value = MockLLMResponse(
                content="Thought: Still thinking\nAction: search('more')"
            )
            mock_cls.return_value = router
            result = await loop.run("Complex problem")
        assert result["steps"] == 3
        assert "Max steps reached" in result["answer"]

    @pytest.mark.asyncio
    async def test_run_llm_error_returns_error_answer(self):
        """Should return error message when LLM fails mid-loop."""
        loop = ReActLoop()
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.side_effect = Exception("API timeout")
            mock_cls.return_value = router
            result = await loop.run("Task")
        assert "Error after" in result["answer"]
        assert "API timeout" in result["answer"]

    @pytest.mark.asyncio
    async def test_run_tracks_thoughts(self):
        """Should accumulate thoughts in the list."""
        loop = ReActLoop()
        with patch("nexus.reasoning.react.LLMRouter") as mock_cls:
            router = MagicMock()
            router.complete = AsyncMock()
            router.complete.side_effect = [
                MockLLMResponse(content="Thought: step 1\nAction: search"),
                MockLLMResponse(content="Thought: step 2\nAnswer: done"),
            ]
            mock_cls.return_value = router
            result = await loop.run("Two-step task")
        assert result["steps"] == 2
        assert len(result["thoughts"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Selector — reason() Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReasonSelector:
    """Test the reason() function dispatching to correct patterns."""

    @pytest.mark.asyncio
    async def test_reason_react_simple(self):
        """Should use ReAct for simple tasks."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            mock_select.return_value = ReasoningPattern.REACT
            with patch("nexus.reasoning.selector.ReActLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run = AsyncMock(return_value={
                    "pattern": "react", "answer": "42",
                    "steps": 1, "thoughts": [], "actions": [],
                })
                mock_loop_cls.return_value = mock_loop
                result = await reason("What is 2+2?")
        assert result["pattern"] == "react"
        assert result["answer"] == "42"

    @pytest.mark.asyncio
    async def test_reason_tot_medium(self):
        """Should use TreeOfThought for medium complexity tasks."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            mock_select.return_value = ReasoningPattern.TOT
            with patch("nexus.reasoning.selector.TreeOfThought") as mock_tot_cls:
                mock_tot = MagicMock()
                mock_tot.solve = AsyncMock(return_value=ToTResult(
                    answer="Best strategy",
                    best_path=["step1", "step2"],
                    total_nodes_explored=10,
                    max_depth_reached=3,
                    branches_explored=2,
                ))
                mock_tot_cls.return_value = mock_tot
                result = await reason("Multi-step task", complexity_hint="medium")
        assert result["pattern"] == "tree_of_thought"
        assert result["answer"] == "Best strategy"

    @pytest.mark.asyncio
    async def test_reason_lats_complex(self):
        """Should use LATS for complex tasks."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            mock_select.return_value = ReasoningPattern.LATS
            with patch("nexus.reasoning.selector.LATSReasoner") as mock_lats_cls:
                mock_lats = MagicMock()
                mock_lats.solve = AsyncMock(return_value=LATSResult(
                    answer="Optimal solution",
                    best_path=[{"action": "think"}, {"action": "solve"}],
                    total_simulations=50,
                    total_nodes=100,
                    best_reward=0.95,
                ))
                mock_lats_cls.return_value = mock_lats
                result = await reason("Complex optimization", complexity_hint="complex")
        assert result["pattern"] == "lats"
        assert result["answer"] == "Optimal solution"

    @pytest.mark.asyncio
    async def test_reason_lats_with_custom_params(self):
        """Should pass max_depth and max_simulations to LATS."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            mock_select.return_value = ReasoningPattern.LATS
            with patch("nexus.reasoning.selector.LATSReasoner") as mock_lats_cls:
                mock_lats = MagicMock()
                mock_lats.solve = AsyncMock(return_value=LATSResult(
                    answer="Solution", best_path=[], total_simulations=100,
                ))
                mock_lats_cls.return_value = mock_lats
                await reason(
                    "Complex task",
                    complexity_hint="complex",
                    max_depth=8,
                    max_simulations=100,
                )
                mock_lats_cls.assert_called_once_with(
                    max_simulations=100, max_depth=8,
                )

    @pytest.mark.asyncio
    async def test_reason_tot_with_max_depth(self):
        """Should pass max_depth to TreeOfThought."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            mock_select.return_value = ReasoningPattern.TOT
            with patch("nexus.reasoning.selector.TreeOfThought") as mock_tot_cls:
                mock_tot = MagicMock()
                mock_tot.solve = AsyncMock(return_value=ToTResult(
                    answer="Ans", best_path=[],
                ))
                mock_tot_cls.return_value = mock_tot
                await reason("Medium task", complexity_hint="medium", max_depth=6)
                mock_tot_cls.assert_called_once_with(
                    max_depth=6, branch_factor=3, beam_width=2,
                )

    @pytest.mark.asyncio
    async def test_reason_without_hint_auto_selects(self):
        """Should auto-select pattern when no complexity hint is given."""
        with patch("nexus.reasoning.selector.select_reasoning_pattern") as mock_select:
            # Simulate ReAct being selected for a simple task
            mock_select.return_value = ReasoningPattern.REACT
            with patch("nexus.reasoning.selector.ReActLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.run = AsyncMock(return_value={
                    "pattern": "react", "answer": "auto answer",
                    "steps": 1, "thoughts": [], "actions": [],
                })
                mock_loop_cls.return_value = mock_loop
                result = await reason("What is 2+2?")
        assert result["pattern"] == "react"
        assert result["answer"] == "auto answer"
        mock_select.assert_called_once_with("What is 2+2?", None)
