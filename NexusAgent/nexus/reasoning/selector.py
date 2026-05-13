"""
NEXUS Reasoning Selector — Adaptive pattern selection with real implementations.

Routes tasks to the optimal reasoning pattern:
  - ReAct: Simple Thought-Action-Observation loop
  - Tree-of-Thought: Multi-branch exploration with evaluation
  - LATS/MCTS: Monte Carlo Tree Search for complex optimization

The selector uses heuristic analysis of the task description
to determine which pattern is most appropriate.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.reasoning.react import ReasoningPattern, ReActLoop, select_reasoning_pattern
from nexus.reasoning.tot import TreeOfThought
from nexus.reasoning.lats import LATSReasoner

logger = logging.getLogger(__name__)


async def reason(
    task: str,
    complexity_hint: Optional[str] = None,
    max_depth: int = 4,
    max_simulations: int = 20,
) -> dict[str, Any]:
    """
    Execute reasoning on a task using the automatically selected pattern.

    All three reasoning patterns (ReAct, ToT, LATS) are fully implemented:
      - ReAct: Fast, single-chain reasoning for simple tasks
      - ToT: Multi-branch exploration for medium-complexity tasks
      - LATS: MCTS-based search for complex optimization tasks

    Args:
        task: The task to reason about.
        complexity_hint: Optional complexity hint to override auto-detection.
        max_depth: Maximum reasoning depth (for ToT/LATS).
        max_simulations: Maximum MCTS simulations (for LATS).

    Returns:
        Result dict with pattern used, answer, and metadata.
    """
    pattern = select_reasoning_pattern(task, complexity_hint)
    logger.info("Selected reasoning pattern: %s for task: %s", pattern.value, task[:100])

    if pattern == ReasoningPattern.REACT:
        loop = ReActLoop()
        result = await loop.run(task)
        result["pattern"] = "react"
        return result

    elif pattern == ReasoningPattern.TOT:
        tot = TreeOfThought(
            max_depth=max_depth,
            branch_factor=3,
            beam_width=2,
        )
        result = await tot.solve(task)
        return {
            "pattern": "tree_of_thought",
            "answer": result.answer,
            "best_path": result.best_path,
            "total_nodes_explored": result.total_nodes_explored,
            "max_depth_reached": result.max_depth_reached,
            "branches_explored": result.branches_explored,
        }

    elif pattern == ReasoningPattern.LATS:
        lats = LATSReasoner(
            max_simulations=max_simulations,
            max_depth=max_depth,
        )
        result = await lats.solve(task)
        return {
            "pattern": "lats",
            "answer": result.answer,
            "best_path": result.best_path,
            "total_simulations": result.total_simulations,
            "total_nodes": result.total_nodes,
            "best_reward": result.best_reward,
        }

    else:
        # Fallback to ReAct
        loop = ReActLoop()
        result = await loop.run(task)
        result["pattern"] = "react"
        return result
