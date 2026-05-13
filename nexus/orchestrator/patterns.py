"""
NEXUS Multi-Agent Patterns — 6 coordination patterns for agent teams.

Implements the following patterns from the APEX specification:
  1. Supervisor: Central agent delegates tasks to subordinates
  2. Pipeline: Sequential chain of agents
  3. Parallel: Multiple agents work simultaneously
  4. Hierarchical: Tree structure with managers and workers
  5. Mesh: Peer-to-peer agent communication
  6. Swarm: Self-organizing agent collective
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from nexus.core.exceptions import OrchestratorError

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    SUPERVISOR = "supervisor"
    PIPELINE = "pipeline"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    MESH = "mesh"
    SWARM = "swarm"


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    assigned_to: str = ""
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class PatternResult:
    """Result from executing a multi-agent pattern."""
    pattern: PatternType
    success: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    execution_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


async def _execute_single_task(
    task: AgentTask,
    agent_handler: Optional[Callable] = None,
) -> dict[str, Any]:
    """Execute a single agent task using the handler or a default implementation."""
    if agent_handler:
        try:
            result = await agent_handler(task.description, task.assigned_to)
            task.status = "completed"
            task.result = str(result)
            return {"task_id": task.task_id, "status": "completed", "result": result}
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            return {"task_id": task.task_id, "status": "failed", "error": str(e)}
    else:
        # Default: use LLM router
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = await router.complete(
                messages=[
                    {"role": "system", "content": f"You are agent '{task.assigned_to}'. Complete the assigned task."},
                    {"role": "user", "content": task.description},
                ],
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.5,
            )
            task.status = "completed"
            task.result = response.content
            return {"task_id": task.task_id, "status": "completed", "result": response.content}
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            return {"task_id": task.task_id, "status": "failed", "error": str(e)}


async def supervisor_pattern(
    main_task: str,
    sub_tasks: list[str],
    supervisor_agent: str = "supervisor",
    worker_agents: list[str] | None = None,
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Supervisor Pattern: Central agent delegates tasks to subordinates.

    The supervisor:
      1. Decomposes the main task
      2. Assigns sub-tasks to workers
      3. Monitors progress
      4. Synthesizes results

    Args:
        main_task: The overall task description.
        sub_tasks: List of sub-task descriptions.
        supervisor_agent: Name of the supervisor agent.
        worker_agents: Names of worker agents.
        agent_handler: Optional function to handle agent execution.

    Returns:
        PatternResult with combined outputs.
    """
    import time
    start = time.monotonic()

    if not worker_agents:
        worker_agents = [f"worker_{i}" for i in range(min(len(sub_tasks), 5))]

    # Create tasks and assign to workers (round-robin)
    tasks = []
    for i, desc in enumerate(sub_tasks):
        task = AgentTask(
            description=desc,
            assigned_to=worker_agents[i % len(worker_agents)],
        )
        tasks.append(task)

    # Execute tasks in parallel (supervisor monitors)
    results = []
    coros = [_execute_single_task(t, agent_handler) for t in tasks]
    task_results = await asyncio.gather(*coros, return_exceptions=True)

    for r in task_results:
        if isinstance(r, Exception):
            results.append({"status": "failed", "error": str(r)})
        else:
            results.append(r)

    # Supervisor synthesizes
    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    # Synthesize results
    synthesis = " | ".join(
        r.get("result", r.get("error", "no result"))[:200]
        for r in results
    )

    return PatternResult(
        pattern=PatternType.SUPERVISOR,
        success=failed == 0,
        results=results,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


async def pipeline_pattern(
    main_task: str,
    stages: list[dict[str, str]],
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Pipeline Pattern: Sequential chain of agents.

    Each stage processes the output of the previous stage:
      Stage 1 → Stage 2 → Stage 3 → ... → Final output

    Args:
        main_task: The overall task.
        stages: List of {"agent": "name", "description": "what this stage does"}.
        agent_handler: Optional handler.

    Returns:
        PatternResult with pipeline outputs.
    """
    import time
    start = time.monotonic()

    results = []
    current_input = main_task

    for i, stage in enumerate(stages):
        task = AgentTask(
            description=f"{stage.get('description', 'Process input')}\n\nInput: {current_input[:2000]}",
            assigned_to=stage.get("agent", f"stage_{i}"),
        )
        result = await _execute_single_task(task, agent_handler)
        results.append(result)

        if result.get("status") == "completed":
            current_input = result.get("result", current_input)
        else:
            # Pipeline breaks on failure
            break

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    return PatternResult(
        pattern=PatternType.PIPELINE,
        success=failed == 0 and completed == len(stages),
        results=results,
        total_tasks=len(stages),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


async def parallel_pattern(
    main_task: str,
    sub_tasks: list[str],
    agents: list[str] | None = None,
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Parallel Pattern: Multiple agents work simultaneously.

    All sub-tasks are executed in parallel, and results are
    combined at the end.

    Args:
        main_task: The overall task.
        sub_tasks: Independent sub-tasks.
        agents: Agent names for assignment.
        agent_handler: Optional handler.

    Returns:
        PatternResult with combined outputs.
    """
    import time
    start = time.monotonic()

    if not agents:
        agents = [f"agent_{i}" for i in range(min(len(sub_tasks), 10))]

    tasks = []
    for i, desc in enumerate(sub_tasks):
        tasks.append(AgentTask(
            description=desc,
            assigned_to=agents[i % len(agents)],
        ))

    coros = [_execute_single_task(t, agent_handler) for t in tasks]
    task_results = await asyncio.gather(*coros, return_exceptions=True)

    results = []
    for r in task_results:
        if isinstance(r, Exception):
            results.append({"status": "failed", "error": str(r)})
        else:
            results.append(r)

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    return PatternResult(
        pattern=PatternType.PARALLEL,
        success=failed == 0,
        results=results,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


async def hierarchical_pattern(
    main_task: str,
    hierarchy: dict[str, Any],
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Hierarchical Pattern: Tree structure with managers and workers.

    The hierarchy defines a tree of agents where each manager
    delegates to its children.

    Args:
        main_task: The overall task.
        hierarchy: Dict defining the tree structure.
        agent_handler: Optional handler.

    Returns:
        PatternResult with hierarchical outputs.
    """
    import time
    start = time.monotonic()

    results = []

    async def _process_node(node: dict[str, Any], task_desc: str, depth: int = 0):
        """Recursively process a hierarchy node."""
        agent_name = node.get("agent", f"manager_{depth}")
        sub_tasks = node.get("sub_tasks", [])
        children = node.get("children", [])

        # Manager processes the task first
        mgr_task = AgentTask(description=task_desc, assigned_to=agent_name)
        mgr_result = await _execute_single_task(mgr_task, agent_handler)
        results.append(mgr_result)

        # Process children in parallel
        if children:
            child_coros = [
                _process_node(child, child.get("task", task_desc), depth + 1)
                for child in children
            ]
            await asyncio.gather(*child_coros)

    await _process_node(hierarchy, main_task)

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    return PatternResult(
        pattern=PatternType.HIERARCHICAL,
        success=failed == 0,
        results=results,
        total_tasks=len(results),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


async def mesh_pattern(
    main_task: str,
    agents: list[str],
    max_rounds: int = 3,
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Mesh Pattern: Peer-to-peer agent communication.

    Agents communicate directly with each other in rounds,
    sharing and building upon each other's findings.

    Args:
        main_task: The overall task.
        agents: List of agent names.
        max_rounds: Maximum communication rounds.
        agent_handler: Optional handler.

    Returns:
        PatternResult with mesh outputs.
    """
    import time
    start = time.monotonic()

    results = []
    shared_context = main_task

    for round_num in range(max_rounds):
        round_results = []

        for agent_name in agents:
            task = AgentTask(
                description=(
                    f"Round {round_num + 1}/{max_rounds}. "
                    f"Shared context so far: {shared_context[:1000]}\n\n"
                    f"Contribute your perspective on: {main_task}"
                ),
                assigned_to=agent_name,
            )
            result = await _execute_single_task(task, agent_handler)
            round_results.append(result)

        # Merge results into shared context for next round
        new_contributions = [
            r.get("result", "")[:500]
            for r in round_results
            if r.get("status") == "completed"
        ]
        shared_context = f"{shared_context}\n\nRound {round_num + 1} contributions:\n" + "\n".join(new_contributions)
        results.extend(round_results)

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    return PatternResult(
        pattern=PatternType.MESH,
        success=failed == 0,
        results=results,
        total_tasks=len(results),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


async def swarm_pattern(
    main_task: str,
    num_agents: int = 5,
    iterations: int = 3,
    agent_handler: Optional[Callable] = None,
) -> PatternResult:
    """
    Swarm Pattern: Self-organizing agent collective.

    Agents self-organize by claiming sub-tasks and collaborating.
    No central coordinator — agents negotiate among themselves.

    Args:
        main_task: The overall task.
        num_agents: Number of agents in the swarm.
        iterations: Number of swarm iterations.
        agent_handler: Optional handler.

    Returns:
        PatternResult with swarm outputs.
    """
    import time
    start = time.monotonic()

    agents = [f"swarm_agent_{i}" for i in range(num_agents)]
    results = []
    accumulated_knowledge = main_task

    for iteration in range(iterations):
        # Each agent independently contributes
        iter_coros = []
        for agent_name in agents:
            task = AgentTask(
                description=(
                    f"Swarm iteration {iteration + 1}/{iterations}. "
                    f"Accumulated knowledge: {accumulated_knowledge[:1500]}\n\n"
                    f"Task: {main_task}\n"
                    f"Contribute your unique perspective or finding."
                ),
                assigned_to=agent_name,
            )
            iter_coros.append(_execute_single_task(task, agent_handler))

        iter_results = await asyncio.gather(*iter_coros, return_exceptions=True)

        iter_data = []
        for r in iter_results:
            if isinstance(r, Exception):
                results.append({"status": "failed", "error": str(r)})
            else:
                results.append(r)
                if r.get("status") == "completed":
                    iter_data.append(r.get("result", ""))

        # Swarm convergence: merge new findings
        if iter_data:
            accumulated_knowledge += "\n\nNew findings:\n" + "\n".join(d[:300] for d in iter_data)

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    return PatternResult(
        pattern=PatternType.SWARM,
        success=failed == 0,
        results=results,
        total_tasks=len(results),
        completed_tasks=completed,
        failed_tasks=failed,
        execution_time_ms=(time.monotonic() - start) * 1000,
    )


# Pattern registry for easy access
PATTERNS = {
    PatternType.SUPERVISOR: supervisor_pattern,
    PatternType.PIPELINE: pipeline_pattern,
    PatternType.PARALLEL: parallel_pattern,
    PatternType.HIERARCHICAL: hierarchical_pattern,
    PatternType.MESH: mesh_pattern,
    PatternType.SWARM: swarm_pattern,
}


async def execute_pattern(
    pattern: PatternType,
    main_task: str,
    **kwargs,
) -> PatternResult:
    """
    Execute a multi-agent pattern by type.

    Args:
        pattern: The pattern type to execute.
        main_task: The main task description.
        **kwargs: Pattern-specific arguments.

    Returns:
        PatternResult from the executed pattern.
    """
    handler = PATTERNS.get(pattern)
    if not handler:
        raise OrchestratorError(f"Unknown pattern: {pattern}")
    return await handler(main_task=main_task, **kwargs)
