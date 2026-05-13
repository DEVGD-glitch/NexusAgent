"""
NEXUS Agent Registry — Central registry for all agent types and instances.

Manages the lifecycle of agents including registration, discovery,
instantiation, and status tracking. Supports both built-in and
custom agent types.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from nexus.core.exceptions import AgentSpawnError

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentCapability(str, Enum):
    RESEARCH = "research"
    CODING = "coding"
    ANALYSIS = "analysis"
    OPERATION = "operation"
    COMMUNICATION = "communication"
    REASONING = "reasoning"
    BROWSING = "browsing"
    FILE_OPS = "file_ops"


@dataclass
class AgentCard:
    """
    Agent Card — A2A-compatible agent descriptor.

    Describes an agent's capabilities, endpoint, and metadata
    following the Agent-to-Agent (A2A) protocol specification.
    """
    agent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    capabilities: list[AgentCapability] = field(default_factory=list)
    endpoint: str = ""
    version: str = "1.0.0"
    provider: str = "nexus"
    skills: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "endpoint": self.endpoint,
            "version": self.version,
            "provider": self.provider,
            "skills": self.skills,
            "metadata": self.metadata,
        }


@dataclass
class AgentInstance:
    """A running instance of an agent."""
    instance_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_type: str = ""
    status: AgentStatus = AgentStatus.IDLE
    task: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class AgentRegistry:
    """
    Central registry for NEXUS agents.

    Manages:
      - Agent type registration (what kinds of agents exist)
      - Agent instantiation (creating instances of agents)
      - Agent discovery (finding agents by capability)
      - Agent status tracking (what each agent is doing)
      - A2A Agent Cards (interoperability with external agents)

    Usage:
        registry = AgentRegistry()
        registry.register_type("researcher", ResearcherAgent)
        agent = registry.spawn("researcher", task="Find recent AI papers")
    """

    def __init__(self):
        self._agent_types: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, AgentInstance] = {}
        self._agent_cards: dict[str, AgentCard] = {}
        self._factories: dict[str, Callable] = {}

    def register_type(
        self,
        type_name: str,
        factory: Optional[Callable] = None,
        capabilities: Optional[list[AgentCapability]] = None,
        description: str = "",
        skills: Optional[list[str]] = None,
    ) -> None:
        """
        Register an agent type in the registry.

        Args:
            type_name: Unique name for the agent type.
            factory: Callable that creates an agent instance.
            capabilities: List of agent capabilities.
            description: Human-readable description.
            skills: List of skill names this agent type can use.
        """
        self._agent_types[type_name] = {
            "name": type_name,
            "factory": factory,
            "capabilities": capabilities or [],
            "description": description,
            "skills": skills or [],
        }

        # Create A2A Agent Card
        card = AgentCard(
            name=type_name,
            description=description,
            capabilities=capabilities or [],
            skills=skills or [],
        )
        self._agent_cards[type_name] = card

        logger.info("Registered agent type: %s (capabilities: %s)", type_name, capabilities)

    def spawn(
        self,
        agent_type: str,
        task: str = "",
        **kwargs,
    ) -> AgentInstance:
        """
        Spawn a new agent instance.

        Args:
            agent_type: Type of agent to spawn.
            task: Task for the agent.

        Returns:
            AgentInstance tracking the spawned agent.

        Raises:
            AgentSpawnError: If the agent type is not registered.
        """
        if agent_type not in self._agent_types:
            raise AgentSpawnError(
                agent_type=agent_type,
                reason=f"Agent type '{agent_type}' not registered. Available: {list(self._agent_types.keys())}",
            )

        instance = AgentInstance(
            agent_type=agent_type,
            task=task,
            status=AgentStatus.IDLE,
        )
        self._instances[instance.instance_id] = instance

        logger.info("Spawned agent %s of type '%s' for task: %s",
                     instance.instance_id, agent_type, task[:100])

        return instance

    def get_instance(self, instance_id: str) -> Optional[AgentInstance]:
        """Get an agent instance by ID."""
        return self._instances.get(instance_id)

    def update_status(self, instance_id: str, status: AgentStatus, **kwargs) -> bool:
        """Update an agent instance's status."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False
        instance.status = status
        if status == AgentStatus.RUNNING and not instance.started_at:
            instance.started_at = datetime.now(timezone.utc).isoformat()
        if status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
            instance.completed_at = datetime.now(timezone.utc).isoformat()
        if "result" in kwargs:
            instance.result = kwargs["result"]
        if "error" in kwargs:
            instance.error = kwargs["error"]
        return True

    def find_by_capability(self, capability: AgentCapability) -> list[str]:
        """Find agent types that have a specific capability."""
        matching = []
        for type_name, info in self._agent_types.items():
            if capability in info.get("capabilities", []):
                matching.append(type_name)
        return matching

    def get_agent_card(self, agent_type: str) -> Optional[AgentCard]:
        """Get the A2A Agent Card for a type."""
        return self._agent_cards.get(agent_type)

    def get_all_cards(self) -> list[dict[str, Any]]:
        """Get all registered A2A Agent Cards."""
        return [card.to_dict() for card in self._agent_cards.values()]

    def list_types(self) -> list[dict[str, Any]]:
        """List all registered agent types."""
        return [
            {
                "name": info["name"],
                "description": info["description"],
                "capabilities": [c.value for c in info["capabilities"]],
                "skills": info["skills"],
                "active_instances": sum(
                    1 for i in self._instances.values()
                    if i.agent_type == info["name"] and i.status == AgentStatus.RUNNING
                ),
            }
            for info in self._agent_types.values()
        ]

    def list_instances(self, status: Optional[AgentStatus] = None) -> list[AgentInstance]:
        """List agent instances, optionally filtered by status."""
        instances = list(self._instances.values())
        if status:
            instances = [i for i in instances if i.status == status]
        return instances

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        status_counts = {}
        for instance in self._instances.values():
            status_counts[instance.status.value] = status_counts.get(instance.status.value, 0) + 1
        return {
            "registered_types": len(self._agent_types),
            "total_instances": len(self._instances),
            "active_instances": sum(1 for i in self._instances.values() if i.status == AgentStatus.RUNNING),
            "status_distribution": status_counts,
        }


# Global registry singleton
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global AgentRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        _register_default_types(_registry)
    return _registry


def _register_default_types(registry: AgentRegistry) -> None:
    """Register the default built-in agent types."""
    registry.register_type(
        "general",
        capabilities=[AgentCapability.REASONING, AgentCapability.FILE_OPS],
        description="General-purpose agent for any task",
    )
    registry.register_type(
        "researcher",
        capabilities=[AgentCapability.RESEARCH, AgentCapability.BROWSING, AgentCapability.REASONING],
        description="Research agent for information gathering and synthesis",
        skills=["web_search", "document_analysis", "fact_checking"],
    )
    registry.register_type(
        "developer",
        capabilities=[AgentCapability.CODING, AgentCapability.FILE_OPS, AgentCapability.REASONING],
        description="Software development agent for writing and debugging code",
        skills=["code_generation", "debugging", "code_review", "testing"],
    )
    registry.register_type(
        "analyst",
        capabilities=[AgentCapability.ANALYSIS, AgentCapability.REASONING],
        description="Data analysis agent for insights and reporting",
        skills=["data_analysis", "visualization", "reporting"],
    )
    registry.register_type(
        "operator",
        capabilities=[AgentCapability.OPERATION, AgentCapability.FILE_OPS, AgentCapability.BROWSING],
        description="Operations agent for system management and automation",
        skills=["system_admin", "deployment", "monitoring"],
    )
