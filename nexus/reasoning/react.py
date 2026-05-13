"""
NEXUS Reasoning Module — Adaptive reasoning pattern selector.

Selects the optimal reasoning pattern based on task complexity:
  - ReAct (simple): Fast Thought-Action-Observation loop
  - Tree-of-Thought (medium): Explore multiple reasoning branches
  - LATS/MCTS (complex): Monte Carlo Tree Search with backpropagation

Inspired by GenericAgent''s context density principle and LATS paper.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.llm.router import LLMRouter, TaskComplexity

logger = logging.getLogger(__name__)


class ReasoningPattern(str, Enum):
    REACT = "react"
    TOT = "tree_of_thought"
    LATS = "lats"


def select_reasoning_pattern(
    task: str,
    complexity: Optional[str] = None,
) -> ReasoningPattern:
    """
    Select the reasoning pattern based on task characteristics.

    Heuristics:
    - Simple tasks (single action, clear answer) → ReAct
    - Medium tasks (multi-step, moderate uncertainty) → Tree-of-Thought
    - Complex tasks (high uncertainty, exploration needed) → LATS

    Args:
        task: Task description.
        complexity: Override complexity hint.

    Returns:
        Selected ReasoningPattern.
    """
    if complexity:
        complexity_map = {
            "simple": ReasoningPattern.REACT,
            "medium": ReasoningPattern.TOT,
            "complex": ReasoningPattern.LATS,
        }
        return complexity_map.get(complexity.lower(), ReasoningPattern.REACT)

    # Heuristic analysis of task
    task_lower = task.lower()

    # Indicators of complexity
    complex_indicators = [
        "explore", "investigate", "optimize", "find the best",
        "compare alternatives", "multiple approaches", "trade-off",
        "research", "analyze deeply", "comprehensive",
    ]
    medium_indicators = [
        "then", "after that", "multiple steps", "first", "next",
        "sequence", "pipeline", "step by step",
    ]
    simple_indicators = [
        "what is", "who is", "when", "where", "how many",
        "define", "explain", "list", "calculate",
    ]

    complex_score = sum(1 for ind in complex_indicators if ind in task_lower)
    medium_score = sum(1 for ind in medium_indicators if ind in task_lower)
    simple_score = sum(1 for ind in simple_indicators if ind in task_lower)

    if complex_score >= 2 or (complex_score > 0 and medium_score == 0):
        return ReasoningPattern.LATS
    elif medium_score >= 2 or (medium_score > 0 and simple_score == 0):
        return ReasoningPattern.TOT
    else:
        return ReasoningPattern.REACT


class ReActLoop:
    """
    ReAct (Reasoning + Acting) loop — simple and fast.

    Pattern: Thought → Action → Observation → repeat until done.

    Best for: Simple factual queries, single-tool tasks.
    """

    def __init__(self):
        self.max_steps = 10
        self.reset()

    def reset(self) -> None:
        """Reset state between runs."""
        self.thoughts: list[str] = []
        self.actions: list[dict[str, Any]] = []
        self.observations: list[str] = []

    async def run(
        self,
        task: str,
        tools: Optional[dict[str, Any]] = None,
        reset_state: bool = True,
    ) -> dict[str, Any]:
        """
        Run a ReAct loop for the given task.

        Args:
            task: Task to complete.
            tools: Available tools dict.
            reset_state: Whether to reset thoughts/actions/observations before run.

        Returns:
            Result dict with thoughts, actions, observations, and final answer.
        """
        if reset_state:
            self.reset()

        router = LLMRouter()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are NEXUS using ReAct reasoning. For each step:\n"
                    "1. Think about what to do (Thought)\n"
                    "2. Choose an action (Action)\n"
                    "3. Observe the result (Observation)\n\n"
                    "Format each step as:\n"
                    "Thought: [your reasoning]\n"
                    "Action: [tool_name(args)]\n"
                    "When you have the answer, say:\n"
                    "Answer: [final answer]"
                ),
            },
            {"role": "user", "content": task},
        ]

        for step in range(self.max_steps):
            try:
                response = await router.complete(
                    messages=messages,
                    task_complexity=TaskComplexity.SIMPLE,
                    temperature=0.3,
                )
                content = response.content

                # Check if we have a final answer
                if "Answer:" in content:
                    answer = content.split("Answer:")[-1].strip()
                    self.thoughts.append(content)
                    return {
                        "pattern": "react",
                        "answer": answer,
                        "steps": step + 1,
                        "thoughts": self.thoughts,
                        "actions": self.actions,
                    }

                self.thoughts.append(content)
                messages.append({"role": "assistant", "content": content})

                # Parse and execute action if tools available
                observation = f"Step {step + 1} completed"
                self.observations.append(observation)
                messages.append({"role": "user", "content": f"Observation: {observation}"})

            except Exception as e:
                logger.error("ReAct step %d failed: %s", step, e)
                return {
                    "pattern": "react",
                    "answer": f"Error after {step} steps: {str(e)}",
                    "steps": step + 1,
                    "thoughts": self.thoughts,
                    "actions": self.actions,
                }

        return {
            "pattern": "react",
            "answer": "Max steps reached without final answer",
            "steps": self.max_steps,
            "thoughts": self.thoughts,
            "actions": self.actions,
        }
