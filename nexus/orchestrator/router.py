"""
NEXUS Dynamic Orchestration Router — Engine selection based on task characteristics.

Analyzes incoming tasks and routes them to the most appropriate orchestration
engine:
  - LangGraph: Structured, deterministic workflows with state machines
  - CrewAI: Collaborative, emergent multi-agent tasks with role-based agents
  - Google ADK: Sequential/parallel pipelines with tool-augmented agents

The router considers task complexity, structure requirements, collaboration
needs, and available engine dependencies to make routing decisions.

Usage:
    from nexus.orchestrator.router import OrchestrationRouter

    router = OrchestrationRouter()
    result = await router.route(task="Build a web scraper and deploy it")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import OrchestratorError

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────

class EngineType(str, Enum):
    """Supported orchestration engine types."""
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    ADK = "adk"


class TaskStructure(str, Enum):
    """Task structure characteristics."""
    STRUCTURED = "structured"       # Clear steps, deterministic flow
    SEMI_STRUCTURED = "semi"        # Some structure, some flexibility
    UNSTRUCTURED = "unstructured"   # Emergent, adaptive approach needed


class CollaborationStyle(str, Enum):
    """How agents should collaborate."""
    SEQUENTIAL = "sequential"       # One after another
    PARALLEL = "parallel"           # Simultaneous work
    COLLABORATIVE = "collaborative" # Working together, discussing
    HIERARCHICAL = "hierarchical"   # Manager delegates to workers


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class TaskAnalysis:
    """Analysis of a task's characteristics for routing."""
    task: str
    complexity: str = "medium"          # simple, medium, complex
    structure: TaskStructure = TaskStructure.SEMI_STRUCTURED
    collaboration: CollaborationStyle = CollaborationStyle.SEQUENTIAL
    requires_determinism: bool = False
    requires_creativity: bool = False
    agent_count: int = 1
    has_sub_tasks: bool = False
    domain: str = "general"
    confidence: float = 0.5
    reasoning: str = ""


@dataclass
class RoutingDecision:
    """A routing decision with metadata."""
    engine: EngineType
    task_analysis: TaskAnalysis
    confidence: float = 0.5
    reasoning: str = ""
    fallback_engine: Optional[EngineType] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "fallback_engine": self.fallback_engine.value if self.fallback_engine else None,
            "complexity": self.task_analysis.complexity,
            "structure": self.task_analysis.structure.value,
            "collaboration": self.task_analysis.collaboration.value,
            "timestamp": self.timestamp,
        }


@dataclass
class RoutingLog:
    """Log entry for a routing decision."""
    task_preview: str
    decision: RoutingDecision
    success: bool = True
    execution_time_ms: float = 0.0
    error: Optional[str] = None


# ── Task Analyzer ─────────────────────────────────────────────────

class TaskAnalyzer:
    """
    Analyzes task characteristics to inform routing decisions.

    Uses keyword analysis and heuristics to determine:
      - Task complexity
      - Task structure
      - Required collaboration style
      - Domain
    """

    # Complexity indicators
    COMPLEXITY_INDICATORS = {
        "simple": [
            "quick", "simple", "basic", "single", "just", "lookup",
            "tell me", "what is", "define", "convert", "format",
        ],
        "complex": [
            "comprehensive", "full", "complete", "end-to-end", "pipeline",
            "multi-step", "complex", "integrate", "architect", "design and build",
            "research and develop", "analyze and report",
        ],
    }

    # Structure indicators
    STRUCTURE_INDICATORS = {
        TaskStructure.STRUCTURED: [
            "pipeline", "workflow", "step by step", "sequential", "stages",
            "phase", "deterministic", "reproducible", "automated",
        ],
        TaskStructure.UNSTRUCTURED: [
            "brainstorm", "explore", "investigate", "creative", "innovative",
            "open-ended", "discover", "emergent", "collaborate", "discuss",
        ],
    }

    # Collaboration indicators
    COLLABORATION_INDICATORS = {
        CollaborationStyle.SEQUENTIAL: [
            "then", "after that", "pipeline", "chain", "sequence",
            "first", "second", "next", "finally",
        ],
        CollaborationStyle.PARALLEL: [
            "simultaneously", "in parallel", "concurrently", "at the same time",
            "both", "all at once",
        ],
        CollaborationStyle.COLLABORATIVE: [
            "collaborate", "discuss", "debate", "review together",
            "consensus", "team", "group", "collective",
        ],
        CollaborationStyle.HIERARCHICAL: [
            "manage", "coordinate", "supervise", "delegate", "assign",
            "oversee", "direct",
        ],
    }

    # Domain indicators
    DOMAIN_INDICATORS = {
        "research": ["research", "investigate", "study", "paper", "literature"],
        "development": ["code", "build", "develop", "implement", "program", "deploy"],
        "analysis": ["analyze", "data", "statistics", "metrics", "insights", "trends"],
        "operations": ["deploy", "monitor", "infrastructure", "system", "server", "devops"],
    }

    def analyze(self, task: str) -> TaskAnalysis:
        """
        Analyze a task and return its characteristics.

        Args:
            task: The task description.

        Returns:
            TaskAnalysis with the analyzed characteristics.
        """
        task_lower = task.lower()

        # Determine complexity
        complexity = "medium"
        for level, keywords in self.COMPLEXITY_INDICATORS.items():
            if any(kw in task_lower for kw in keywords):
                complexity = level
                break

        # Estimate agent count from complexity
        agent_count = 1
        if complexity == "complex":
            agent_count = 3
        elif complexity == "medium":
            agent_count = 2

        # Check for explicit multi-agent indicators
        multi_agent_indicators = ["and", "then", "also", "plus", "with", "multiple agents", "team"]
        explicit_multi = sum(1 for ind in multi_agent_indicators if ind in task_lower)
        if explicit_multi >= 2:
            agent_count = max(agent_count, 3)

        # Determine structure
        structure = TaskStructure.SEMI_STRUCTURED
        for struct, keywords in self.STRUCTURE_INDICATORS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                structure = struct
                break

        # Determine collaboration style
        collaboration = CollaborationStyle.SEQUENTIAL
        best_collab_score = 0
        for collab, keywords in self.COLLABORATION_INDICATORS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > best_collab_score:
                best_collab_score = score
                collaboration = collab

        # Determine domain
        domain = "general"
        best_domain_score = 0
        for d, keywords in self.DOMAIN_INDICATORS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > best_domain_score:
                best_domain_score = score
                domain = d

        # Determine special requirements
        requires_determinism = any(
            kw in task_lower for kw in ["reproducible", "deterministic", "exact", "precise", "automated"]
        )
        requires_creativity = any(
            kw in task_lower for kw in ["creative", "innovative", "brainstorm", "design", "novel"]
        )

        # Check for sub-tasks
        has_sub_tasks = any(
            kw in task_lower for kw in ["and then", "after that", "next", "also", "plus", "as well as"]
        ) or agent_count > 1

        # Compute confidence
        indicator_count = sum([
            1 if complexity != "medium" else 0,
            1 if structure != TaskStructure.SEMI_STRUCTURED else 0,
            1 if best_collab_score > 0 else 0,
            1 if domain != "general" else 0,
        ])
        confidence = min(0.5 + indicator_count * 0.125, 0.95)

        reasoning_parts = []
        reasoning_parts.append(f"Complexity: {complexity}")
        reasoning_parts.append(f"Structure: {structure.value}")
        reasoning_parts.append(f"Collaboration: {collaboration.value}")
        reasoning_parts.append(f"Domain: {domain}")
        reasoning_parts.append(f"Agent count: {agent_count}")
        if requires_determinism:
            reasoning_parts.append("Requires determinism")
        if requires_creativity:
            reasoning_parts.append("Requires creativity")

        return TaskAnalysis(
            task=task,
            complexity=complexity,
            structure=structure,
            collaboration=collaboration,
            requires_determinism=requires_determinism,
            requires_creativity=requires_creativity,
            agent_count=agent_count,
            has_sub_tasks=has_sub_tasks,
            domain=domain,
            confidence=confidence,
            reasoning="; ".join(reasoning_parts),
        )


# ── Engine Availability ───────────────────────────────────────────

def _check_engine_available(engine: EngineType) -> bool:
    """Check if a specific engine's dependencies are available."""
    if engine == EngineType.LANGGRAPH:
        try:
            import langgraph  # noqa: F401
            return True
        except ImportError:
            return False
    elif engine == EngineType.CREWAI:
        try:
            import crewai  # noqa: F401
            return True
        except ImportError:
            return False
    elif engine == EngineType.ADK:
        try:
            import google.adk  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def get_available_engines() -> dict[str, bool]:
    """Get availability status of all engines."""
    return {
        engine.value: _check_engine_available(engine)
        for engine in EngineType
    }


# ── Main Router ───────────────────────────────────────────────────

class OrchestrationRouter:
    """
    Dynamic orchestration router that selects the best engine for each task.

    Routing Logic:
      - LangGraph: Best for structured, deterministic workflows with
        state machines, checkpoints, and human-in-the-loop.
      - CrewAI: Best for collaborative, emergent tasks where agents
        have defined roles and work together creatively.
      - Google ADK: Best for sequential/parallel pipelines with
        tool-augmented agents and session management.

    All engines fall back to NEXUS-native execution when their
    dependencies are not installed.

    Usage:
        router = OrchestrationRouter()
        decision = router.analyze("Build and deploy a web application")
        result = await router.execute(decision, task="Build and deploy...")
    """

    def __init__(self):
        self.settings = get_settings()
        self.analyzer = TaskAnalyzer()
        self._routing_log: list[RoutingLog] = []
        self._tasks_routed: int = 0

    def analyze(self, task: str) -> RoutingDecision:
        """
        Analyze a task and determine the best engine.

        Args:
            task: The task description.

        Returns:
            RoutingDecision with the selected engine and reasoning.
        """
        analysis = self.analyzer.analyze(task)

        # ── Routing Decision Logic ──

        engine = EngineType.LANGGRAPH  # Default
        fallback = EngineType.CREWAI
        reasoning = []

        # Rule 1: Structured + deterministic → LangGraph
        if analysis.structure == TaskStructure.STRUCTURED or analysis.requires_determinism:
            engine = EngineType.LANGGRAPH
            reasoning.append("Task is structured/requires determinism → LangGraph")
            fallback = EngineType.ADK

        # Rule 2: Unstructured + collaborative + creative → CrewAI
        elif (
            analysis.structure == TaskStructure.UNSTRUCTURED
            and analysis.collaboration in (CollaborationStyle.COLLABORATIVE,)
        ) or analysis.requires_creativity:
            engine = EngineType.CREWAI
            reasoning.append("Task is unstructured/collaborative/creative → CrewAI")
            fallback = EngineType.LANGGRAPH

        # Rule 3: Hierarchical delegation → LangGraph or CrewAI
        elif analysis.collaboration == CollaborationStyle.HIERARCHICAL:
            if analysis.requires_determinism:
                engine = EngineType.LANGGRAPH
                reasoning.append("Hierarchical + deterministic → LangGraph")
            else:
                engine = EngineType.CREWAI
                reasoning.append("Hierarchical + flexible → CrewAI")
            fallback = EngineType.ADK

        # Rule 4: Sequential pipeline → ADK
        elif analysis.collaboration == CollaborationStyle.SEQUENTIAL and analysis.has_sub_tasks:
            engine = EngineType.ADK
            reasoning.append("Sequential pipeline with sub-tasks → ADK")
            fallback = EngineType.LANGGRAPH

        # Rule 5: Parallel execution → ADK
        elif analysis.collaboration == CollaborationStyle.PARALLEL:
            engine = EngineType.ADK
            reasoning.append("Parallel execution → ADK")
            fallback = EngineType.LANGGRAPH

        # Rule 6: Simple task → LangGraph (lightweight)
        elif analysis.complexity == "simple":
            engine = EngineType.LANGGRAPH
            reasoning.append("Simple task → LangGraph (lightweight)")
            fallback = EngineType.ADK

        # Rule 7: Default → LangGraph (most general)
        else:
            engine = EngineType.LANGGRAPH
            reasoning.append("Default → LangGraph (most general)")
            fallback = EngineType.CREWAI

        # Check engine availability — fall back if primary unavailable
        if not _check_engine_available(engine):
            reasoning.append(f"Primary engine {engine.value} not available")
            if _check_engine_available(fallback):
                engine, fallback = fallback, engine
                reasoning.append(f"Falling back to {engine.value}")
            else:
                # Find any available engine
                for eng in EngineType:
                    if _check_engine_available(eng):
                        engine = eng
                        reasoning.append(f"Using available engine: {engine.value}")
                        break

        # Compute confidence
        confidence = analysis.confidence
        if not _check_engine_available(engine):
            confidence *= 0.5  # Lower confidence when falling back

        decision = RoutingDecision(
            engine=engine,
            task_analysis=analysis,
            confidence=confidence,
            reasoning=analysis.reasoning + " | " + "; ".join(reasoning),
            fallback_engine=fallback,
        )

        logger.info(
            "Routing decision: engine=%s confidence=%.2f task='%s'",
            engine.value, confidence, task[:80],
        )

        return decision

    async def execute(
        self,
        task: str,
        decision: Optional[RoutingDecision] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute a task using the selected engine.

        Args:
            task: The task description.
            decision: Optional pre-computed routing decision.
            **kwargs: Additional parameters for the engine.

        Returns:
            Dict with execution results.
        """
        self._tasks_routed += 1
        start = time.monotonic()

        if decision is None:
            decision = self.analyze(task)

        engine = decision.engine

        try:
            result = await self._dispatch_to_engine(engine, task, **kwargs)

            # Log successful execution
            log_entry = RoutingLog(
                task_preview=task[:200],
                decision=decision,
                success=True,
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
            self._routing_log.append(log_entry)

            result["routing_decision"] = decision.to_dict()
            return result

        except Exception as e:
            logger.error("Engine %s failed for task: %s", engine.value, e)

            # Try fallback engine
            if decision.fallback_engine:
                logger.info("Trying fallback engine: %s", decision.fallback_engine.value)
                try:
                    result = await self._dispatch_to_engine(
                        decision.fallback_engine, task, **kwargs
                    )

                    log_entry = RoutingLog(
                        task_preview=task[:200],
                        decision=decision,
                        success=True,
                        execution_time_ms=(time.monotonic() - start) * 1000,
                    )
                    self._routing_log.append(log_entry)

                    result["routing_decision"] = decision.to_dict()
                    result["used_fallback"] = True
                    return result

                except Exception as fallback_err:
                    logger.error("Fallback engine also failed: %s", fallback_err)

            # Both engines failed
            log_entry = RoutingLog(
                task_preview=task[:200],
                decision=decision,
                success=False,
                execution_time_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )
            self._routing_log.append(log_entry)

            return {
                "status": "failed",
                "error": str(e),
                "routing_decision": decision.to_dict(),
            }

    async def _dispatch_to_engine(
        self,
        engine: EngineType,
        task: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Dispatch a task to a specific engine.

        Args:
            engine: The engine to use.
            task: The task description.
            **kwargs: Additional parameters.

        Returns:
            Dict with execution results.
        """
        if engine == EngineType.LANGGRAPH:
            from nexus.orchestrator.langgraph_engine import run_nexus_task
            result = await run_nexus_task(
                task=task,
                messages=kwargs.get("messages"),
                thread_id=kwargs.get("thread_id"),
            )
            result["engine"] = "langgraph"
            return result

        elif engine == EngineType.CREWAI:
            from nexus.orchestrator.crewai_engine import CrewAIEngine, AGENT_TEMPLATES
            engine_instance = CrewAIEngine()

            # Determine agents based on task
            task_lower = task.lower()
            agents = ["researcher"]
            if any(kw in task_lower for kw in ["code", "develop", "build", "implement", "debug"]):
                agents.append("developer")
            if any(kw in task_lower for kw in ["analyze", "data", "report", "insight"]):
                agents.append("analyst")
            if any(kw in task_lower for kw in ["deploy", "monitor", "system", "automate"]):
                agents.append("operator")

            tasks = [{"description": task, "expected_output": "Complete task result", "agent_role": agents[0]}]

            result = await engine_instance.run_crew(
                agents=agents,
                tasks=tasks,
                process=kwargs.get("process", "sequential"),
            )
            result["engine"] = "crewai"
            return result

        elif engine == EngineType.ADK:
            from nexus.orchestrator.adk_engine import ADKEngine, ADKAgentConfig
            engine_instance = ADKEngine()

            # Create agent config based on task
            agent_config = ADKAgentConfig(
                name="nexus_task_agent",
                description="NEXUS task execution agent",
                instruction="Complete the assigned task using available tools.",
            )

            result = await engine_instance.run_agent(
                agent_config=agent_config,
                task=task,
                session_id=kwargs.get("session_id"),
            )
            result["engine"] = "adk"
            return result

        else:
            raise OrchestratorError(f"Unknown engine type: {engine}")

    def get_routing_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent routing decisions."""
        return [
            {
                "task_preview": log.task_preview,
                "engine": log.decision.engine.value,
                "success": log.success,
                "execution_time_ms": log.execution_time_ms,
                "error": log.error,
            }
            for log in self._routing_log[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        total = len(self._routing_log)
        successful = sum(1 for log in self._routing_log if log.success)

        engine_counts: dict[str, int] = {}
        for log in self._routing_log:
            engine_name = log.decision.engine.value
            engine_counts[engine_name] = engine_counts.get(engine_name, 0) + 1

        avg_time = (
            sum(log.execution_time_ms for log in self._routing_log) / total
            if total > 0 else 0
        )

        return {
            "tasks_routed": self._tasks_routed,
            "total_decisions": total,
            "success_rate": successful / total if total > 0 else 0,
            "engine_distribution": engine_counts,
            "avg_execution_time_ms": round(avg_time, 2),
            "available_engines": get_available_engines(),
        }
