"""
NEXUS LATS Reasoning — Language Agent Tree Search with Monte Carlo Tree Search.

Implements the LATS (Language Agent Tree Search) reasoning pattern
combining LLM-based reasoning with Monte Carlo Tree Search (MCTS).
Based on the LATS paper (Zhou et al., 2023).

LATS uses MCTS to balance exploration and exploitation:
  1. Selection: Use UCB1 to select the most promising node
  2. Expansion: Generate child nodes from the selected node
  3. Simulation: Roll out a trajectory from the new node
  4. Backpropagation: Update values up the tree

This is the most sophisticated reasoning pattern, suitable for
complex tasks requiring deep exploration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MCTSNode:
    """A node in the MCTS tree."""
    state: str  # Current state description
    action: str  # Action that led to this state
    parent: Optional["MCTSNode"] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0  # Accumulated reward
    depth: int = 0
    is_terminal: bool = False
    reward: float = 0.0  # Immediate reward for this state

    @property
    def q_value(self) -> float:
        """Average reward (Q-value)."""
        if self.visits == 0:
            return 0.0
        return self.value / self.visits

    def ucb1(self, exploration_weight: float = 1.414) -> float:
        """
        Upper Confidence Bound 1 score for selection.

        Balances exploitation (high Q-value) with exploration
        (low visit count).
        """
        if self.visits == 0:
            return float("inf")
        if self.parent is None or self.parent.visits == 0:
            return self.q_value
        exploitation = self.q_value
        exploration = exploration_weight * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )
        return exploitation + exploration

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action[:100],
            "q_value": round(self.q_value, 3),
            "visits": self.visits,
            "depth": self.depth,
            "is_terminal": self.is_terminal,
            "reward": self.reward,
            "children_count": len(self.children),
        }


@dataclass
class LATSResult:
    """Result from a LATS reasoning session."""
    answer: str
    best_path: list[dict[str, Any]]
    total_simulations: int = 0
    total_nodes: int = 0
    best_reward: float = 0.0
    tree_stats: dict[str, Any] = field(default_factory=dict)


class LATSReasoner:
    """
    Language Agent Tree Search (LATS) with MCTS.

    Combines LLM-based reasoning with Monte Carlo Tree Search
    for optimal decision-making in complex tasks.

    Parameters:
        max_simulations: Maximum number of MCTS simulations.
        max_depth: Maximum tree depth.
        exploration_weight: UCB1 exploration parameter (sqrt(2) default).
        rollout_depth: Depth of rollout simulations.
        num_actions: Number of candidate actions to generate at each node.

    Usage:
        lats = LATSReasoner(max_simulations=20, max_depth=5)
        result = await lats.solve("Find the optimal architecture for this system")
        print(result.answer)
    """

    def __init__(
        self,
        max_simulations: int = 20,
        max_depth: int = 5,
        exploration_weight: float = 1.414,
        rollout_depth: int = 3,
        num_actions: int = 3,
    ):
        self.max_simulations = max_simulations
        self.max_depth = max_depth
        self.exploration_weight = exploration_weight
        self.rollout_depth = rollout_depth
        self.num_actions = num_actions
        self._total_nodes = 0
        self._llm_router = None

    async def solve(
        self,
        task: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> LATSResult:
        """
        Solve a task using LATS/MCTS.

        Args:
            task: The task description.
            context: Optional prior conversation messages.

        Returns:
            LATSResult with the best answer found.
        """
        self._total_nodes = 0

        # Initialize root node
        root = MCTSNode(state=task, action="initial_task", depth=0)
        self._total_nodes = 1

        best_node = root
        best_reward = -1.0

        # Run MCTS simulations
        for sim in range(self.max_simulations):
            # Step 1: Selection — traverse tree using UCB1
            selected = self._select(root)

            # Step 2: Expansion — add child nodes
            if not selected.is_terminal and selected.visits > 0:
                await self._expand(selected, task, context)

            # Step 3: Simulation — rollout from a child
            rollout_node = selected
            if selected.children:
                rollout_node = random.choice(selected.children)
                reward = await self._simulate(rollout_node, task, context)
            else:
                reward = await self._evaluate_state(selected, task)

            # Step 4: Backpropagation — update values up the tree
            self._backpropagate(rollout_node, reward)

            # Track best solution
            if reward > best_reward:
                best_reward = reward
                if selected.children:
                    best_child = max(selected.children, key=lambda n: n.q_value)
                    if best_child.reward > best_node.reward:
                        best_node = best_child
                else:
                    best_node = selected

            logger.debug(
                "LATS simulation %d/%d: reward=%.2f best=%.2f nodes=%d",
                sim + 1, self.max_simulations, reward, best_reward, self._total_nodes,
            )

        # Extract the best path
        best_path = self._trace_path(best_node)

        # Get the answer from the best leaf
        answer = await self._extract_answer(best_node, task)

        return LATSResult(
            answer=answer,
            best_path=best_path,
            total_simulations=self.max_simulations,
            total_nodes=self._total_nodes,
            best_reward=best_reward,
            tree_stats=self._get_tree_stats(root),
        )

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Select the most promising node using UCB1."""
        while node.children:
            # Pick child with highest UCB1 score
            unvisited = [c for c in node.children if c.visits == 0]
            if unvisited:
                return random.choice(unvisited)
            node = max(node.children, key=lambda c: c.ucb1(self.exploration_weight))
        return node

    async def _expand(
        self,
        node: MCTSNode,
        task: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> None:
        """Expand a node by generating candidate actions."""
        if node.depth >= self.max_depth:
            node.is_terminal = True
            return

        actions = await self._generate_actions(node, task, context)

        for action in actions:
            child = MCTSNode(
                state=action,
                action=action,
                parent=node,
                depth=node.depth + 1,
            )
            node.children.append(child)
            self._total_nodes += 1

    async def _simulate(
        self,
        node: MCTSNode,
        task: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> float:
        """
        Run a rollout simulation from the given node.

        Performs a quick evaluation by estimating the value of
        continuing from this state.
        """
        current = node
        cumulative_reward = 0.0
        discount = 0.9

        for step in range(self.rollout_depth):
            if current.is_terminal:
                break

            # Evaluate current state
            reward = await self._evaluate_state(current, task)
            cumulative_reward += reward * (discount ** step)

            # Generate one-step lookahead
            actions = await self._generate_actions(current, task, context, num=1)
            if not actions:
                break

            # Create virtual child for next step
            current = MCTSNode(
                state=actions[0],
                action=actions[0],
                depth=current.depth + 1,
            )

        # Final evaluation
        final_reward = await self._evaluate_state(current, task)
        cumulative_reward += final_reward * (discount ** self.rollout_depth)

        return cumulative_reward / (self.rollout_depth + 1)

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        """Backpropagate reward up the tree."""
        current = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent

    def _get_router(self):
        """Get or create cached LLM router."""
        if self._llm_router is None:
            from nexus.llm.router import LLMRouter
            self._llm_router = LLMRouter()
        return self._llm_router

    async def _generate_actions(
        self,
        node: MCTSNode,
        task: str,
        context: Optional[list[dict[str, str]]] = None,
        num: Optional[int] = None,
    ) -> list[str]:
        """Generate candidate actions for a given state."""
        effective_num = num or self.num_actions

        try:
            from nexus.llm.router import TaskComplexity
            router = self._get_router()

            # Build path context
            path_so_far = []
            current = node
            while current.parent is not None:
                path_so_far.append(current.action)
                current = current.parent
            path_so_far.reverse()

            prompt = (
                f"You are using LATS (Language Agent Tree Search) reasoning.\n"
                f"Task: {task}\n"
            )
            if path_so_far:
                prompt += f"Steps taken so far: {' -> '.join(path_so_far[-5:])}\n"
            prompt += (
                f"Current state: {node.state[:200]}\n\n"
                f"Generate {effective_num} distinct next actions to try.\n"
                f"Each action should be a concrete step toward solving the task.\n"
                f"If the task is solved, write 'SOLUTION: <answer>'.\n"
                f"Output as a numbered list."
            )

            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.8,
                max_tokens=512,
            )

            actions = []
            for line in response.content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean:
                        actions.append(clean)

            return actions[:effective_num]

        except Exception as e:
            logger.error("LATS action generation failed: %s", e)
            return []

    async def _evaluate_state(
        self,
        node: MCTSNode,
        task: str,
    ) -> float:
        """Evaluate a state, returning a reward between 0 and 1."""
        try:
            from nexus.llm.router import TaskComplexity
            router = self._get_router()

            prompt = (
                f"Evaluate this reasoning state for the task on a scale of 0 to 1.\n"
                f"Task: {task}\n"
                f"Current state: {node.state[:200]}\n\n"
                f"Rate the progress toward solving the task.\n"
                f"0 = no progress / dead end, 1 = task fully solved.\n"
                f"Output ONLY a decimal number between 0 and 1."
            )

            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.1,
                max_tokens=10,
            )

            text = response.content.strip()
            try:
                score = float(text)
                return max(0.0, min(1.0, score))
            except ValueError:
                # Try to extract a number
                import re
                numbers = re.findall(r'0?\.\d+|[01]', text)
                if numbers:
                    return max(0.0, min(1.0, float(numbers[0])))
                return 0.5

        except Exception as e:
            logger.error("LATS state evaluation failed: %s", e)
            return 0.5

    async def _extract_answer(self, node: MCTSNode, task: str) -> str:
        """Extract the final answer from the best node."""
        if "SOLUTION:" in node.state:
            return node.state.split("SOLUTION:")[-1].strip()
        if "Answer:" in node.state:
            return node.state.split("Answer:")[-1].strip()

        # Use LLM to synthesize answer from the best path
        try:
            from nexus.llm.router import TaskComplexity
            router = self._get_router()

            path = self._trace_path(node)
            path_text = "\n".join(f"Step {i+1}: {step['action']}" for i, step in enumerate(path))

            prompt = (
                f"Based on the following reasoning steps, provide a final answer.\n"
                f"Task: {task}\n"
                f"Reasoning path:\n{path_text}\n\n"
                f"Provide a clear, concise final answer."
            )

            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.3,
                max_tokens=512,
            )
            return response.content
        except Exception:
            return node.state

    def _trace_path(self, node: MCTSNode) -> list[dict[str, Any]]:
        """Trace the path from root to a given node."""
        path = []
        current = node
        while current is not None:
            path.append(current.to_dict())
            current = current.parent
        path.reverse()
        return path

    def _get_tree_stats(self, root: MCTSNode) -> dict[str, Any]:
        """Get statistics about the MCTS tree."""
        all_nodes = []
        queue = [root]
        while queue:
            node = queue.pop(0)
            all_nodes.append(node)
            queue.extend(node.children)

        return {
            "total_nodes": len(all_nodes),
            "max_depth": max((n.depth for n in all_nodes), default=0),
            "avg_visits": sum(n.visits for n in all_nodes) / max(len(all_nodes), 1),
            "terminal_nodes": sum(1 for n in all_nodes if n.is_terminal),
        }
