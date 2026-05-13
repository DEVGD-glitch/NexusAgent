"""
NEXUS Tree-of-Thought (ToT) Reasoning — Multi-branch exploration.

Implements the Tree-of-Thought reasoning pattern where the agent
explores multiple reasoning branches, evaluates each, and selects
the most promising path. Based on the ToT paper (Yao et al., 2023).

Unlike ReAct which follows a single chain, ToT:
  1. Generates multiple candidate thoughts at each step
  2. Evaluates each thought's promise
  3. Prunes low-scoring branches
  4. Explores the best branches deeper
  5. Backtracks when a path leads to a dead end
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ThoughtNode:
    """A single node in the reasoning tree."""
    thought: str
    score: float = 0.0
    depth: int = 0
    children: list["ThoughtNode"] = field(default_factory=list)
    parent: Optional["ThoughtNode"] = None
    is_solution: bool = False
    evaluation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "thought": self.thought,
            "score": self.score,
            "depth": self.depth,
            "is_solution": self.is_solution,
            "evaluation": self.evaluation,
            "children_count": len(self.children),
        }


@dataclass
class ToTResult:
    """Result from a Tree-of-Thought reasoning session."""
    answer: str
    best_path: list[str]
    total_nodes_explored: int = 0
    max_depth_reached: int = 0
    branches_explored: int = 0
    tree_snapshot: dict[str, Any] = field(default_factory=dict)


class TreeOfThought:
    """
    Tree-of-Thought reasoning engine.

    Explores multiple reasoning paths in parallel, evaluates each,
    and uses best-first search to find the optimal solution.

    Parameters:
        max_depth: Maximum depth of the reasoning tree.
        branch_factor: Number of candidate thoughts to generate at each step.
        evaluation_threshold: Minimum score (0-10) to continue exploring a branch.
        beam_width: Number of top branches to keep at each depth level.

    Usage:
        tot = TreeOfThought(max_depth=4, branch_factor=3)
        result = await tot.solve("Find the optimal strategy for resource allocation")
        print(result.answer)
    """

    def __init__(
        self,
        max_depth: int = 4,
        branch_factor: int = 3,
        evaluation_threshold: float = 5.0,
        beam_width: int = 2,
    ):
        self.max_depth = max_depth
        self.branch_factor = branch_factor
        self.evaluation_threshold = evaluation_threshold
        self.beam_width = beam_width
        self._total_nodes = 0

    async def solve(
        self,
        task: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> ToTResult:
        """
        Solve a task using Tree-of-Thought reasoning.

        Args:
            task: The task description.
            context: Optional prior conversation messages.

        Returns:
            ToTResult with the best answer and reasoning path.
        """
        self._total_nodes = 0

        # Step 1: Generate initial candidate thoughts
        root = ThoughtNode(thought=task, depth=0)
        initial_thoughts = await self._generate_thoughts(
            task=task, depth=0, context=context,
        )

        if not initial_thoughts:
            return ToTResult(
                answer="Could not generate initial thoughts for this task",
                best_path=[task],
                total_nodes_explored=0,
            )

        # Step 2: Evaluate and score initial thoughts
        scored_thoughts = []
        for thought_text in initial_thoughts:
            score = await self._evaluate_thought(thought_text, task, depth=0)
            node = ThoughtNode(
                thought=thought_text,
                score=score,
                depth=1,
                parent=root,
            )
            root.children.append(node)
            scored_thoughts.append(node)
            self._total_nodes += 1

        # Step 3: Beam search — keep top branches
        current_beam = sorted(scored_thoughts, key=lambda n: n.score, reverse=True)[:self.beam_width]

        # Step 4: Expand each branch up to max_depth
        best_solution_node: Optional[ThoughtNode] = None
        best_solution_score = -1.0

        for depth in range(2, self.max_depth + 1):
            next_beam = []

            for node in current_beam:
                # Check if this node is a solution
                if node.is_solution and node.score > best_solution_score:
                    best_solution_node = node
                    best_solution_score = node.score

                # Skip branches below threshold
                if node.score < self.evaluation_threshold:
                    continue

                # Generate child thoughts
                child_thoughts = await self._generate_thoughts(
                    task=task,
                    depth=depth,
                    previous_thought=node.thought,
                    context=context,
                )

                for thought_text in child_thoughts:
                    score = await self._evaluate_thought(
                        thought_text, task, depth=depth,
                        previous_thought=node.thought,
                    )
                    child = ThoughtNode(
                        thought=thought_text,
                        score=score,
                        depth=depth,
                        parent=node,
                        is_solution="answer:" in thought_text.lower() or "solution:" in thought_text.lower(),
                    )
                    node.children.append(child)
                    next_beam.append(child)
                    self._total_nodes += 1

            if not next_beam:
                break

            # Keep top beam_width nodes for next level
            current_beam = sorted(next_beam, key=lambda n: n.score, reverse=True)[:self.beam_width]

            # Check if any current beam node is a solution
            for node in current_beam:
                if node.is_solution and node.score > best_solution_score:
                    best_solution_node = node
                    best_solution_score = node.score

        # If no explicit solution found, use the best-scoring leaf
        if not best_solution_node:
            all_leaves = self._get_all_leaves(root)
            if all_leaves:
                best_solution_node = max(all_leaves, key=lambda n: n.score)
            else:
                best_solution_node = root

        # Trace the best path from root to solution
        best_path = self._trace_path(best_solution_node)

        return ToTResult(
            answer=best_solution_node.thought,
            best_path=best_path,
            total_nodes_explored=self._total_nodes,
            max_depth_reached=best_solution_node.depth,
            branches_explored=len(root.children),
            tree_snapshot=self._tree_to_dict(root),
        )

    async def _generate_thoughts(
        self,
        task: str,
        depth: int,
        previous_thought: Optional[str] = None,
        context: Optional[list[dict[str, str]]] = None,
    ) -> list[str]:
        """Generate candidate thoughts at a given depth."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()

            if depth == 0:
                prompt = (
                    f"You are using Tree-of-Thought reasoning. For the task below, "
                    f"generate {self.branch_factor} different approaches or first steps.\n\n"
                    f"Task: {task}\n\n"
                    f"Output {self.branch_factor} approaches as a numbered list. "
                    f"Each approach should be a distinct strategy."
                )
            else:
                prompt = (
                    f"You are using Tree-of-Thought reasoning at depth {depth}.\n"
                    f"Task: {task}\n"
                    f"Previous reasoning step: {previous_thought}\n\n"
                    f"Generate {self.branch_factor} possible next steps. "
                    f"If you have found the answer, start with 'Answer:'.\n"
                    f"Output as a numbered list."
                )

            messages = [{"role": "user", "content": prompt}]
            response = await router.complete(
                messages=messages,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=1024,
            )

            # Parse numbered list
            thoughts = []
            for line in response.content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean:
                        thoughts.append(clean)

            return thoughts[:self.branch_factor]

        except Exception as e:
            logger.error("ToT thought generation failed at depth %d: %s", depth, e)
            return []

    async def _evaluate_thought(
        self,
        thought: str,
        task: str,
        depth: int,
        previous_thought: Optional[str] = None,
    ) -> float:
        """Evaluate and score a thought on a scale of 0-10."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()

            prompt = (
                f"Evaluate this reasoning step for the task on a scale of 0-10.\n"
                f"Task: {task}\n"
            )
            if previous_thought:
                prompt += f"Previous step: {previous_thought}\n"
            prompt += (
                f"Current step: {thought}\n\n"
                f"Rate how promising this step is (0=dead end, 10=perfect solution).\n"
                f"If this step provides a complete answer, rate it 9 or 10.\n"
                f"Output ONLY a single number between 0 and 10."
            )

            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.1,
                max_tokens=10,
            )

            # Parse score
            text = response.content.strip()
            for char in text:
                if char.isdigit():
                    score = int(char)
                    return float(min(score, 10))
            return 5.0  # Default middle score

        except Exception as e:
            logger.error("ToT evaluation failed: %s", e)
            return 5.0

    def _get_all_leaves(self, root: ThoughtNode) -> list[ThoughtNode]:
        """Get all leaf nodes in the tree."""
        leaves = []
        if not root.children:
            leaves.append(root)
        else:
            for child in root.children:
                leaves.extend(self._get_all_leaves(child))
        return leaves

    def _trace_path(self, node: ThoughtNode) -> list[str]:
        """Trace the path from root to a given node."""
        path = []
        current = node
        while current is not None:
            path.append(current.thought)
            current = current.parent
        path.reverse()
        return path

    def _tree_to_dict(self, node: ThoughtNode, max_depth: int = 3) -> dict[str, Any]:
        """Convert tree to a serializable dict (limited depth for readability)."""
        result = {
            "thought": node.thought[:100],
            "score": node.score,
            "depth": node.depth,
        }
        if node.depth < max_depth and node.children:
            result["children"] = [self._tree_to_dict(c, max_depth) for c in node.children]
        return result
