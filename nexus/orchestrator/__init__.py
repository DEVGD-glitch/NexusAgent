"""NEXUS Orchestrator — Multi-engine orchestration."""

from nexus.orchestrator.langgraph_engine import run_nexus_task, build_nexus_graph
from nexus.orchestrator.patterns import (
    supervisor_pattern,
    pipeline_pattern,
    parallel_pattern,
    hierarchical_pattern,
    mesh_pattern,
    swarm_pattern,
    execute_pattern,
    PatternType,
)

__all__ = [
    "run_nexus_task",
    "build_nexus_graph",
    "supervisor_pattern",
    "pipeline_pattern",
    "parallel_pattern",
    "hierarchical_pattern",
    "mesh_pattern",
    "swarm_pattern",
    "execute_pattern",
    "PatternType",
    "OrchestrationRouter",
]


def __getattr__(name):
    """Lazy import for optional modules."""
    if name == "OrchestrationRouter":
        from nexus.orchestrator.router import OrchestrationRouter
        return OrchestrationRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
