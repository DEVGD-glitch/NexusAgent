"""NEXUS Agents — Specialized agent types and integration layers."""

from nexus.agents.base import BaseAgent, AgentContext, AgentResult, AgentPhase
from nexus.agents.researcher import ResearcherAgent
from nexus.agents.developer import DeveloperAgent
from nexus.agents.analyst import AnalystAgent
from nexus.agents.operator import OperatorAgent

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "AgentPhase",
    "ResearcherAgent",
    "DeveloperAgent",
    "AnalystAgent",
    "OperatorAgent",
    "OpenAIAgentsLayer",
]


# Agent type registry for dynamic spawning
AGENT_TYPE_MAP: dict[str, type[BaseAgent]] = {
    "researcher": ResearcherAgent,
    "developer": DeveloperAgent,
    "analyst": AnalystAgent,
    "operator": OperatorAgent,
}


def __getattr__(name):
    """Lazy import for optional modules."""
    if name == "OpenAIAgentsLayer":
        from nexus.agents.openai_layer import OpenAIAgentsLayer
        return OpenAIAgentsLayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
