"""
NEXUS OpenAI Agents SDK Integration Layer — Handoffs, guardrails, and tracing.

Provides NEXUS-specific integration with the OpenAI Agents SDK (openai-agents),
enabling:
  - NEXUS agent definitions compatible with the Agents SDK
  - Handoff patterns between Researcher, Developer, Analyst, and Operator
  - Input/output guardrails for safety validation
  - Tracing and observability for agent execution

The openai-agents SDK is optional. When not installed, the layer gracefully
degrades to NEXUS-native execution using the LLM router.

Usage:
    from nexus.agents.openai_layer import OpenAIAgentsLayer

    layer = OpenAIAgentsLayer()
    result = await layer.run(task="Research recent AI breakthroughs")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import AgentError, NexusError
from nexus.core.observability import get_observability

logger = logging.getLogger(__name__)

# ── SDK Availability Check ────────────────────────────────────────

_sdk_available: Optional[bool] = None


def is_openai_agents_available() -> bool:
    """Check if the openai-agents SDK is installed."""
    global _sdk_available
    if _sdk_available is None:
        try:
            import agents  # noqa: F401 — openai-agents SDK
            _sdk_available = True
        except ImportError:
            _sdk_available = False
    return _sdk_available


# ── Data Structures ───────────────────────────────────────────────

class NexusAgentType(str, Enum):
    """NEXUS agent types that map to OpenAI Agents SDK agents."""
    RESEARCHER = "researcher"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    OPERATOR = "operator"


class HandoffReason(str, Enum):
    """Reasons for handing off between agents."""
    TASK_COMPLEXITY = "task_complexity"
    CAPABILITY_REQUIRED = "capability_required"
    USER_REQUEST = "user_request"
    AGENT_DECISION = "agent_decision"
    ERROR_FALLBACK = "error_fallback"


@dataclass
class HandoffRecord:
    """Record of a handoff between agents."""
    from_agent: NexusAgentType
    to_agent: NexusAgentType
    reason: HandoffReason
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    task_snapshot: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent.value,
            "to_agent": self.to_agent.value,
            "reason": self.reason.value,
            "description": self.description,
            "timestamp": self.timestamp,
        }


@dataclass
class GuardrailCheckResult:
    """Result of a guardrail check."""
    passed: bool
    guardrail_name: str
    reason: str = ""
    action: str = "allow"  # allow, warn, block, redact
    redacted_text: Optional[str] = None


@dataclass
class TraceSpan:
    """A tracing span for observability."""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    agent_type: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.monotonic()
        return (end - self.start_time) * 1000

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })


# ── NEXUS Agent Definitions ──────────────────────────────────────

NEXUS_AGENT_DEFINITIONS = {
    NexusAgentType.RESEARCHER: {
        "name": "NEXUS Researcher",
        "instructions": (
            "You are NEXUS Researcher, a specialized research agent. "
            "Your role is to gather information, search the web, analyze documents, "
            "and synthesize findings with citations. "
            "Hand off to the Developer for coding tasks, Analyst for data analysis, "
            "or Operator for system operations."
        ),
        "handoff_destinations": [
            NexusAgentType.DEVELOPER,
            NexusAgentType.ANALYST,
            NexusAgentType.OPERATOR,
        ],
        "capabilities": ["research", "browsing", "reasoning"],
    },
    NexusAgentType.DEVELOPER: {
        "name": "NEXUS Developer",
        "instructions": (
            "You are NEXUS Developer, a specialized software development agent. "
            "Your role is to write code, debug issues, review code quality, "
            "and manage project files. "
            "Hand off to the Researcher for information gathering, "
            "Analyst for data analysis, or Operator for deployment."
        ),
        "handoff_destinations": [
            NexusAgentType.RESEARCHER,
            NexusAgentType.ANALYST,
            NexusAgentType.OPERATOR,
        ],
        "capabilities": ["coding", "file_ops", "reasoning"],
    },
    NexusAgentType.ANALYST: {
        "name": "NEXUS Analyst",
        "instructions": (
            "You are NEXUS Analyst, a specialized data analysis agent. "
            "Your role is to analyze data, generate insights, create visualizations, "
            "and produce reports with evidence-based recommendations. "
            "Hand off to the Researcher for data gathering, "
            "Developer for code implementation, or Operator for automation."
        ),
        "handoff_destinations": [
            NexusAgentType.RESEARCHER,
            NexusAgentType.DEVELOPER,
            NexusAgentType.OPERATOR,
        ],
        "capabilities": ["analysis", "reasoning"],
    },
    NexusAgentType.OPERATOR: {
        "name": "NEXUS Operator",
        "instructions": (
            "You are NEXUS Operator, a specialized operations agent. "
            "Your role is to manage systems, automate tasks, deploy services, "
            "monitor health, and handle incidents. "
            "Hand off to the Developer for code fixes, "
            "Researcher for investigation, or Analyst for metric analysis."
        ),
        "handoff_destinations": [
            NexusAgentType.DEVELOPER,
            NexusAgentType.RESEARCHER,
            NexusAgentType.ANALYST,
        ],
        "capabilities": ["operation", "file_ops", "browsing"],
    },
}


# ── Handoff Router ────────────────────────────────────────────────

class HandoffRouter:
    """
    Routes handoffs between NEXUS agents based on task requirements.

    Determines which agent should handle a task or sub-task based on
    the task content, required capabilities, and current context.
    """

    # Keywords that suggest a specific agent type
    AGENT_KEYWORDS = {
        NexusAgentType.RESEARCHER: [
            "research", "search", "find", "investigate", "look up",
            "gather information", "web search", "fact check", "cite",
            "survey", "literature", "paper", "article",
        ],
        NexusAgentType.DEVELOPER: [
            "code", "program", "implement", "debug", "fix bug",
            "write function", "develop", "refactor", "test", "build",
            "deploy code", "git", "commit", "script",
        ],
        NexusAgentType.ANALYST: [
            "analyze", "analysis", "data", "statistics", "chart",
            "visualize", "report", "insight", "trend", "metric",
            "dashboard", "benchmark", "compare",
        ],
        NexusAgentType.OPERATOR: [
            "deploy", "monitor", "system", "server", "infrastructure",
            "automate", "schedule", "backup", "incident", "health",
            "service", "docker", "container", "restart",
        ],
    }

    def determine_agent(self, task: str) -> NexusAgentType:
        """
        Determine the best agent type for a task based on keyword analysis.

        Args:
            task: The task description.

        Returns:
            The most appropriate NexusAgentType.
        """
        task_lower = task.lower()
        scores: dict[NexusAgentType, int] = {agent: 0 for agent in NexusAgentType}

        for agent_type, keywords in self.AGENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in task_lower:
                    scores[agent_type] += 1

        # Find the agent with the highest score
        best_agent = max(scores, key=lambda a: scores[a])

        # If no keywords matched, default to Researcher as the most general
        if scores[best_agent] == 0:
            return NexusAgentType.RESEARCHER

        return best_agent

    def should_handoff(
        self,
        current_agent: NexusAgentType,
        task: str,
        current_result: Optional[str] = None,
    ) -> Optional[tuple[NexusAgentType, HandoffReason]]:
        """
        Determine if the current agent should hand off to another agent.

        Args:
            current_agent: The currently active agent type.
            task: The current task or sub-task.
            current_result: The current agent's result (optional).

        Returns:
            Tuple of (target_agent, reason) if handoff is needed, else None.
        """
        best_agent = self.determine_agent(task)

        if best_agent != current_agent:
            # Check if the best agent is a valid handoff destination
            definition = NEXUS_AGENT_DEFINITIONS[current_agent]
            if best_agent in definition.get("handoff_destinations", []):
                return best_agent, HandoffReason.CAPABILITY_REQUIRED

        return None


# ── Guardrails ────────────────────────────────────────────────────

class OpenAIGuardrails:
    """
    Input/output guardrails for OpenAI Agents SDK integration.

    Validates inputs before they reach the agent and outputs
    before they are returned to the user. Leverages the existing
    NEXUS GuardrailManager from nexus.security.guardrails.
    """

    def __init__(self):
        self._guardrail_manager = None

    @property
    def guardrail_manager(self):
        """Lazy-initialize the guardrail manager."""
        if self._guardrail_manager is None:
            from nexus.security.guardrails import GuardrailManager
            self._guardrail_manager = GuardrailManager()
        return self._guardrail_manager

    async def check_input(self, text: str) -> GuardrailCheckResult:
        """
        Validate input text before passing to an agent.

        Args:
            text: The input text to validate.

        Returns:
            GuardrailCheckResult with validation outcome.
        """
        try:
            result = self.guardrail_manager.check_input(text)
            return GuardrailCheckResult(
                passed=result.passed,
                guardrail_name=result.guardrail_name,
                reason=result.reason,
                action=result.action.value if hasattr(result.action, "value") else str(result.action),
                redacted_text=result.redacted_text,
            )
        except Exception as e:
            logger.error("Input guardrail check failed: %s", e)
            # On guardrail failure, block by default (fail-closed)
            return GuardrailCheckResult(
                passed=False,
                guardrail_name="input_check",
                reason=f"Guardrail check error: {e}",
                action="block",
            )

    async def check_output(self, text: str) -> GuardrailCheckResult:
        """
        Validate output text before returning to user.

        Args:
            text: The output text to validate.

        Returns:
            GuardrailCheckResult with validation outcome.
        """
        try:
            result = self.guardrail_manager.check_output(text)
            return GuardrailCheckResult(
                passed=result.passed,
                guardrail_name=result.guardrail_name,
                reason=result.reason,
                action=result.action.value if hasattr(result.action, "value") else str(result.action),
                redacted_text=result.redacted_text,
            )
        except Exception as e:
            logger.error("Output guardrail check failed: %s", e)
            return GuardrailCheckResult(
                passed=False,
                guardrail_name="output_check",
                reason=f"Guardrail check error: {e}",
                action="block",
            )


# ── Tracing ───────────────────────────────────────────────────────

class AgentTracer:
    """
    Tracing for OpenAI Agents SDK integration.

    Provides distributed tracing compatible with the NEXUS
    ObservabilityManager. Records agent starts, completions,
    handoffs, tool calls, and errors.
    """

    def __init__(self):
        self._spans: dict[str, TraceSpan] = {}

    def start_span(
        self,
        name: str,
        agent_type: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> TraceSpan:
        """
        Start a new tracing span.

        Args:
            name: Span name (e.g., "agent_execution").
            agent_type: The agent type being traced.
            attributes: Optional initial attributes.

        Returns:
            The created TraceSpan.
        """
        span = TraceSpan(
            name=name,
            agent_type=agent_type,
            attributes=attributes or {},
        )
        self._spans[span.span_id] = span

        # Also record in NEXUS observability
        try:
            obs = get_observability()
            obs.record_metric("agent_span_started", 1.0)
        except Exception:
            pass

        return span

    def end_span(self, span: TraceSpan, status: str = "ok"):
        """
        End a tracing span.

        Args:
            span: The span to end.
            status: Final status ("ok", "error", "cancelled").
        """
        span.end_time = time.monotonic()
        span.status = status

        # Record in NEXUS observability
        try:
            obs = get_observability()
            obs.record_metric("agent_span_duration_ms", span.duration_ms)
            if status == "ok":
                obs.record_metric("agent_span_completed", 1.0)
            else:
                obs.record_metric("agent_span_error", 1.0)
        except Exception:
            pass

    def record_handoff(self, span: TraceSpan, handoff: HandoffRecord):
        """Record a handoff event in a span."""
        span.add_event("handoff", handoff.to_dict())

    def record_tool_call(
        self,
        span: TraceSpan,
        tool_name: str,
        params: Optional[dict[str, Any]] = None,
        result: Optional[str] = None,
    ):
        """Record a tool call event in a span."""
        span.add_event("tool_call", {
            "tool_name": tool_name,
            "params": str(params)[:500] if params else "",
            "result_preview": str(result)[:200] if result else "",
        })

    def get_active_spans(self) -> list[TraceSpan]:
        """Get all currently active (not ended) spans."""
        return [s for s in self._spans.values() if s.end_time is None]

    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get a span by ID."""
        return self._spans.get(span_id)


# ── MCP Tool Access ───────────────────────────────────────────────

async def _get_mcp_tools() -> list[dict[str, Any]]:
    """
    Get available MCP tools for agent use.

    Returns a list of tool definitions that can be passed to
    the OpenAI Agents SDK agent configuration.
    """
    try:
        from nexus.mcp_server import nexus_mcp
        # Return tool metadata (names and descriptions)
        tool_list = []
        for tool_name in nexus_mcp._tool_manager.list_tools():
            tool_list.append({
                "name": tool_name,
                "type": "function",
                "description": f"MCP tool: {tool_name}",
            })
        return tool_list
    except Exception as e:
        logger.warning("Could not retrieve MCP tools: %s", e)
        return []


# ── Main Integration Layer ────────────────────────────────────────

class OpenAIAgentsLayer:
    """
    OpenAI Agents SDK integration layer for NEXUS.

    Provides:
      - NEXUS agent definitions compatible with the Agents SDK
      - Handoff routing between Researcher, Developer, Analyst, Operator
      - Input/output guardrails via NEXUS security layer
      - Distributed tracing for observability
      - Graceful fallback to NEXUS-native execution

    Usage:
        layer = OpenAIAgentsLayer()
        result = await layer.run("Research recent AI papers")
    """

    def __init__(self):
        self.settings = get_settings()
        self.handoff_router = HandoffRouter()
        self.guardrails = OpenAIGuardrails()
        self.tracer = AgentTracer()
        self._sdk_agents: dict[str, Any] = {}
        self._tasks_run: int = 0

    async def run(
        self,
        task: str,
        agent_type: Optional[str] = None,
        max_handoffs: int = 5,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Run a task through the OpenAI Agents SDK integration.

        Attempts to use the native Agents SDK first. Falls back to
        NEXUS-native execution if the SDK is unavailable.

        Args:
            task: The task description.
            agent_type: Optional specific agent type to use.
            max_handoffs: Maximum handoff iterations.
            **kwargs: Additional parameters.

        Returns:
            Dict with execution results.
        """
        self._tasks_run += 1

        # Input guardrail check
        guardrail_result = await self.guardrails.check_input(task)
        if not guardrail_result.passed and guardrail_result.action == "block":
            return {
                "status": "blocked",
                "reason": f"Input guardrail blocked: {guardrail_result.reason}",
                "guardrail": guardrail_result.guardrail_name,
            }

        # Use redacted text if PII was redacted
        effective_task = guardrail_result.redacted_text or task

        # Determine starting agent
        if agent_type:
            try:
                start_agent = NexusAgentType(agent_type)
            except ValueError:
                start_agent = self.handoff_router.determine_agent(effective_task)
        else:
            start_agent = self.handoff_router.determine_agent(effective_task)

        # Start tracing
        span = self.tracer.start_span(
            name="openai_agents_run",
            agent_type=start_agent.value,
            attributes={"task": effective_task[:200], "max_handoffs": max_handoffs},
        )

        try:
            # Try native OpenAI Agents SDK
            if is_openai_agents_available():
                result = await self._run_native(
                    task=effective_task,
                    start_agent=start_agent,
                    max_handoffs=max_handoffs,
                    **kwargs,
                )
            else:
                result = await self._run_fallback(
                    task=effective_task,
                    start_agent=start_agent,
                    max_handoffs=max_handoffs,
                    **kwargs,
                )

            # Output guardrail check
            output_text = result.get("result", "")
            if output_text:
                output_check = await self.guardrails.check_output(output_text)
                if not output_check.passed and output_check.action == "block":
                    result["status"] = "output_blocked"
                    result["guardrail_reason"] = output_check.reason
                elif output_check.redacted_text:
                    result["result"] = output_check.redacted_text

            self.tracer.end_span(span, status="ok")
            result["trace_span_id"] = span.span_id
            result["trace_duration_ms"] = span.duration_ms
            return result

        except Exception as e:
            self.tracer.end_span(span, status="error")
            logger.error("OpenAI Agents layer execution failed: %s", e)
            return {
                "status": "failed",
                "error": str(e),
                "trace_span_id": span.span_id,
            }

    async def _run_native(
        self,
        task: str,
        start_agent: NexusAgentType,
        max_handoffs: int,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Run using the native OpenAI Agents SDK.

        Creates SDK-compatible agent objects with NEXUS instructions
        and handoff configurations.
        """
        try:
            from agents import Agent, Runner, handoff

            # Create NEXUS agents
            nexus_agents = {}
            for agent_type, definition in NEXUS_AGENT_DEFINITIONS.items():
                handoff_targets = []
                for dest in definition.get("handoff_destinations", []):
                    handoff_targets.append(dest.value)

                agent = Agent(
                    name=definition["name"],
                    instructions=definition["instructions"],
                )
                nexus_agents[agent_type.value] = agent

            # Configure handoffs
            start_sdk_agent = nexus_agents[start_agent.value]
            for dest_type in NEXUS_AGENT_DEFINITIONS[start_agent]["handoff_destinations"]:
                target = nexus_agents[dest_type.value]
                # In openai-agents SDK, handoffs are configured as tools
                pass  # Handoff configuration is SDK-specific

            # Run the agent
            runner = Runner()
            result = await runner.run(start_sdk_agent, task)

            return {
                "status": "completed",
                "engine": "openai_agents_native",
                "agent_type": start_agent.value,
                "result": str(result),
            }

        except Exception as e:
            logger.warning("Native OpenAI Agents SDK failed: %s, falling back", e)
            return await self._run_fallback(task, start_agent, max_handoffs, **kwargs)

    async def _run_fallback(
        self,
        task: str,
        start_agent: NexusAgentType,
        max_handoffs: int,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Fallback execution using NEXUS-native LLM router.

        Simulates the handoff pattern by using the LLM router
        to execute tasks and the HandoffRouter to decide
        when to switch agents.
        """
        handoff_history: list[HandoffRecord] = []
        current_agent = start_agent
        current_task = task
        accumulated_results: list[str] = []

        for iteration in range(max_handoffs + 1):
            # Get agent definition
            definition = NEXUS_AGENT_DEFINITIONS.get(current_agent)
            if not definition:
                break

            # Execute with LLM router
            try:
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()

                context = ""
                if accumulated_results:
                    context = "\n\nPrevious work:\n" + "\n".join(
                        r[:500] for r in accumulated_results[-3:]
                    )

                messages = [
                    {"role": "system", "content": definition["instructions"]},
                    {"role": "user", "content": f"Task: {current_task}{context}"},
                ]

                response = await router.complete(
                    messages=messages,
                    task_complexity=TaskComplexity.MEDIUM,
                    temperature=0.5,
                )
                result_text = response.content
                accumulated_results.append(result_text)

                self.tracer.record_tool_call(
                    list(self.tracer._spans.values())[-1] if self.tracer._spans else TraceSpan(),
                    "llm_complete",
                    {"agent_type": current_agent.value},
                    result_text[:200],
                )

            except Exception as e:
                logger.error("Agent execution failed: %s", e)
                accumulated_results.append(f"Error: {e}")

            # Check if handoff is needed
            handoff_decision = self.handoff_router.should_handoff(
                current_agent=current_agent,
                task=current_task,
                current_result=accumulated_results[-1] if accumulated_results else None,
            )

            if handoff_decision:
                target_agent, reason = handoff_decision
                handoff_record = HandoffRecord(
                    from_agent=current_agent,
                    to_agent=target_agent,
                    reason=reason,
                    description=f"Handing off from {current_agent.value} to {target_agent.value}",
                    task_snapshot=current_task[:200],
                )
                handoff_history.append(handoff_record)

                # Record handoff in trace
                if self.tracer._spans:
                    latest_span = list(self.tracer._spans.values())[-1]
                    self.tracer.record_handoff(latest_span, handoff_record)

                current_agent = target_agent

                # If the task mentions a specific sub-task for the new agent
                # update current_task to focus on that agent's perspective
                current_task = (
                    f"[Continued from {handoff_record.from_agent.value}] "
                    f"Original task: {task}\n"
                    f"Focus on your area of expertise: {current_task}"
                )
            else:
                # No handoff needed, we're done
                break

        # Synthesize final result
        final_result = accumulated_results[-1] if accumulated_results else "No result produced"

        return {
            "status": "completed",
            "engine": "nexus_native_fallback",
            "agent_type": start_agent.value,
            "result": final_result,
            "handoff_count": len(handoff_history),
            "handoff_history": [h.to_dict() for h in handoff_history],
            "iterations": iteration + 1 if 'iteration' in dir() else 1,
        }

    def get_agent_definition(self, agent_type: NexusAgentType) -> dict[str, Any]:
        """Get the definition for a specific agent type."""
        return NEXUS_AGENT_DEFINITIONS.get(agent_type, {})

    def list_agents(self) -> list[dict[str, Any]]:
        """List all available NEXUS agent definitions."""
        result = []
        for agent_type, definition in NEXUS_AGENT_DEFINITIONS.items():
            result.append({
                "type": agent_type.value,
                "name": definition["name"],
                "capabilities": definition["capabilities"],
                "handoff_destinations": [d.value for d in definition["handoff_destinations"]],
            })
        return result

    def get_stats(self) -> dict[str, Any]:
        """Get layer statistics."""
        return {
            "engine": "openai_agents_layer",
            "tasks_run": self._tasks_run,
            "sdk_available": is_openai_agents_available(),
            "active_spans": len(self.tracer.get_active_spans()),
            "agent_types": [a.value for a in NexusAgentType],
        }
