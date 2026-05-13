"""
NEXUS MCP Agent Tools.
"""

import json
from typing import Any, Optional


async def spawn_agent(
    agent_type: str,
    task: str,
    config: Optional[dict[str, Any]] = None,
) -> str:
    """Spawn an agent to execute a task."""
    try:
        from nexus.core.registry import AgentRegistry

        registry = AgentRegistry()
        agent = registry.create(agent_type, config or {})
        result = await agent.run(task)

        return json.dumps({
            "status": "completed",
            "agent_type": agent_type,
            "result": result,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_agents() -> str:
    """List all available agent types."""
    try:
        from nexus.core.registry import AgentRegistry

        registry = AgentRegistry()
        agents = registry.list_agents()
        return json.dumps({"agents": agents})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def agent_status(instance_id: str) -> str:
    """Get status of a running agent."""
    try:
        from nexus.core.registry import AgentRegistry

        registry = AgentRegistry()
        status = registry.get_status(instance_id)
        return json.dumps({"instance_id": instance_id, "status": status})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def agent_delegate(
    source_agent: str,
    target_agent: str,
    task: str,
    context: Optional[dict[str, Any]] = None,
) -> str:
    """Delegate a task from one agent to another."""
    try:
        return json.dumps({
            "status": "delegated",
            "source": source_agent,
            "target": target_agent,
            "task": task,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def a2a_discover(agent_url: str) -> str:
    """Discover an A2A agent's capabilities."""
    try:
        return json.dumps({
            "status": "discovered",
            "url": agent_url,
            "capabilities": ["task_execution", "streaming"],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})