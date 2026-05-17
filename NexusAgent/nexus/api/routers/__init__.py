"""NEXUS API Routers."""
from nexus.api.routers import (
    chat, memory, agents, tools, mcp, plugins, rules,
    workflows, voice, viz, approvals, config, metrics, health
)

__all__ = [
    "chat", "memory", "agents", "tools", "mcp", "plugins",
    "rules", "workflows", "voice", "viz", "approvals",
    "config", "metrics", "health"
]
