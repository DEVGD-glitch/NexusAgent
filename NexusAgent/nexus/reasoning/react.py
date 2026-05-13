"""
NEXUS Reasoning Module — Adaptive reasoning pattern selector.

Selects the optimal reasoning pattern based on task complexity:
  - ReAct (simple): Fast Thought-Action-Observation loop
  - Tree-of-Thought (medium): Explore multiple reasoning branches
  - LATS/MCTS (complex): Monte Carlo Tree Search with backpropagation

Inspired by GenericAgent''s context density principle and LATS paper.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, Callable, Optional

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


def _build_tool_registry_from_mcp() -> dict[str, Callable]:
    """
    Build a tool registry from the MCP tools module.

    Returns a dict mapping tool_name → async callable.
    Uses lazy imports to avoid circular dependencies.
    """
    try:
        from nexus.mcp_tools import get_all_tools
        tools = get_all_tools()
        registry: dict[str, Callable] = {}
        for name, fn in tools:
            registry[name] = fn
        return registry
    except Exception as exc:
        logger.warning("Failed to build tool registry from MCP: %s", exc)
        return {}


class ReActLoop:
    """
    ReAct (Reasoning + Acting) loop — simple and fast.

    Pattern: Thought → Action → Observation → repeat until done.

    Best for: Simple factual queries, single-tool tasks.

    Now supports actual tool execution via a tool_registry parameter.
    When the LLM generates an Action: line, the tool is looked up
    in the registry, called with the extracted arguments, and the
    result is fed back as an Observation.
    """

    def __init__(
        self,
        tool_registry: Optional[dict[str, Callable]] = None,
        max_iterations: int = 10,
    ):
        """
        Initialize the ReAct loop.

        Args:
            tool_registry: Dict mapping tool_name → async callable.
                If None, tools are loaded from nexus.mcp_tools on first use.
            max_iterations: Maximum number of Thought-Action-Observation cycles.
        """
        self._explicit_registry = tool_registry
        self.max_iterations = max_iterations
        self._lazy_registry: Optional[dict[str, Callable]] = None
        self.reset()

    @property
    def tool_registry(self) -> dict[str, Callable]:
        """Lazily resolve the tool registry."""
        if self._explicit_registry is not None:
            return self._explicit_registry
        if self._lazy_registry is None:
            self._lazy_registry = _build_tool_registry_from_mcp()
        return self._lazy_registry

    def reset(self) -> None:
        """Reset state between runs."""
        self.thoughts: list[str] = []
        self.actions: list[dict[str, Any]] = []
        self.observations: list[str] = []

    def _parse_action(self, content: str) -> Optional[tuple[str, str]]:
        """
        Parse an Action: line from LLM output.

        Supports formats:
            Action: tool_name
            Action: tool_name(args)
            Action: tool_name(arg1="val1", arg2="val2")

        Returns:
            (tool_name, args_json_string) or None if no action found.
        """
        # Match "Action: tool_name" possibly followed by parentheses
        action_match = re.search(
            r'Action:\s*(\w+)\s*(?:\((.*)\))?\s*$',
            content,
            re.MULTILINE,
        )
        if not action_match:
            return None

        tool_name = action_match.group(1)
        args_raw = action_match.group(2) or ""

        if not args_raw.strip():
            return tool_name, "{}"

        # Try to parse as JSON first
        try:
            json.loads(args_raw)
            return tool_name, args_raw
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to parse as key=value pairs
        args: dict[str, Any] = {}
        for pair in re.finditer(r'(\w+)\s*=\s*("([^"]*)"|\'([^\']*)\'|(\S+))', args_raw):
            key = pair.group(1)
            value = pair.group(3) or pair.group(4) or pair.group(5)
            # Try numeric conversion
            try:
                value = int(value)
            except (ValueError, TypeError):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass
            args[key] = value

        return tool_name, json.dumps(args)

    async def _execute_tool(self, tool_name: str, args_json: str) -> str:
        """
        Execute a tool from the registry and return the observation string.

        Args:
            tool_name: Name of the tool to call.
            args_json: JSON string of arguments.

        Returns:
            Observation string from the tool result.
        """
        registry = self.tool_registry

        if tool_name not in registry:
            available = sorted(registry.keys())[:20]
            return (
                f"Error: Unknown tool '{tool_name}'. "
                f"Available tools: {', '.join(available)}"
                f"{' ...' if len(registry) > 20 else ''}"
            )

        try:
            args = json.loads(args_json) if args_json and args_json != "{}" else {}
        except (json.JSONDecodeError, TypeError) as exc:
            return f"Error: Invalid action arguments '{args_json}': {exc}"

        try:
            fn = registry[tool_name]
            if asyncio.iscoroutinefunction(fn):
                result = await fn(**args)
            else:
                result = fn(**args)

            # Normalize result to string
            if isinstance(result, dict) or isinstance(result, list):
                observation = json.dumps(result, default=str, ensure_ascii=False)
                # Truncate very long observations
                if len(observation) > 3000:
                    observation = observation[:3000] + "... [truncated]"
            else:
                observation = str(result)
                if len(observation) > 3000:
                    observation = observation[:3000] + "... [truncated]"

            return observation

        except TypeError as exc:
            logger.warning("Tool %s called with wrong params: %s", tool_name, exc)
            return f"Error calling tool '{tool_name}': {exc}"
        except Exception as exc:
            logger.error("Tool '%s' execution failed: %s", tool_name, exc)
            return f"Error executing tool '{tool_name}': {exc}"

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
            tools: Available tools dict (overrides constructor registry for this run).
            reset_state: Whether to reset thoughts/actions/observations before run.

        Returns:
            Result dict with thoughts, actions, observations, and final answer.
        """
        if reset_state:
            self.reset()

        # If tools are passed to run(), use them as the registry for this run
        if tools is not None:
            self._explicit_registry = tools

        router = LLMRouter()

        # Build the tool list for the system prompt
        tool_names = sorted(self.tool_registry.keys())
        tool_list_str = ", ".join(tool_names[:30])
        if len(tool_names) > 30:
            tool_list_str += f" ... ({len(tool_names)} total)"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are NEXUS using ReAct reasoning. For each step:\n"
                    "1. Think about what to do (Thought)\n"
                    "2. Choose an action from the available tools (Action)\n"
                    "3. Observe the result (Observation)\n\n"
                    "Available tools: " + tool_list_str + "\n\n"
                    "Format each step as:\n"
                    "Thought: [your reasoning]\n"
                    "Action: tool_name(key=\"value\")\n"
                    "When you have the final answer, say:\n"
                    "Answer: [final answer]\n\n"
                    "Important: Only use tools from the available tools list. "
                    "Use Action: tool_name(args) to call a tool. "
                    "The observation will be provided automatically."
                ),
            },
            {"role": "user", "content": task},
        ]

        for step in range(self.max_iterations):
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
                        "observations": self.observations,
                    }

                self.thoughts.append(content)
                messages.append({"role": "assistant", "content": content})

                # Parse the action from the LLM response
                parsed = self._parse_action(content)

                if parsed is not None:
                    tool_name, args_json = parsed
                    self.actions.append({
                        "tool": tool_name,
                        "args": args_json,
                        "step": step + 1,
                    })

                    # Execute the tool and get the observation
                    observation = await self._execute_tool(tool_name, args_json)
                else:
                    # No action found — prompt the LLM to use the format
                    observation = (
                        "No action was detected. Please use the format:\n"
                        "Thought: [your reasoning]\n"
                        "Action: tool_name(key=\"value\")\n"
                        "Or if you have the answer:\n"
                        "Answer: [final answer]"
                    )

                self.observations.append(observation)
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })

            except Exception as e:
                logger.error("ReAct step %d failed: %s", step, e)
                return {
                    "pattern": "react",
                    "answer": f"Error after {step} steps: {str(e)}",
                    "steps": step + 1,
                    "thoughts": self.thoughts,
                    "actions": self.actions,
                    "observations": self.observations,
                }

        return {
            "pattern": "react",
            "answer": "Max steps reached without final answer",
            "steps": self.max_iterations,
            "thoughts": self.thoughts,
            "actions": self.actions,
            "observations": self.observations,
        }


# Need asyncio import for iscoroutinefunction check
import asyncio
