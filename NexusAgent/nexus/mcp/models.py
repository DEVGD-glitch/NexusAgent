"""
NEXUS MCP Marketplace — Data models.

Defines the data structures used to represent external MCP servers
in the registry and marketplace.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MCPStatus(str, Enum):
    """Lifecycle status of an installed MCP server."""

    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class MCPTrustLevel(str, Enum):
    """Trust / safety level assigned to an MCP server."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


@dataclass
class MCPDefinition:
    """Descriptor for an external MCP server.

    Each MCP server is a standalone process that communicates via the
    Model Context Protocol (stdin/stdout JSON-RPC or Streamable HTTP).
    """

    # ── Identity ──────────────────────────────────────────────────
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    repository: str = ""

    # ── Execution ─────────────────────────────────────────────────
    command: str = ""  # e.g. "node", "python", "uvx"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    # ── Lifecycle ─────────────────────────────────────────────────
    status: MCPStatus = MCPStatus.DISABLED
    trust_level: MCPTrustLevel = MCPTrustLevel.UNKNOWN

    # ── Metadata ──────────────────────────────────────────────────
    token_cost_estimate: float = 0.0
    permissions: list[str] = field(default_factory=list)
    # e.g. ["network", "filesystem:read", "filesystem:write"]

    # ── Auto-generated ────────────────────────────────────────────
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    install_source: str = ""  # "builtin", "github", "url"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for API responses (no secrets in env)."""
        safe_env = {k: "***" for k in self.env} if self.env else {}
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "repository": self.repository,
            "command": self.command,
            "args": self.args,
            "env_keys": list(self.env.keys()),
            "status": self.status.value,
            "trust_level": self.trust_level.value,
            "token_cost_estimate": self.token_cost_estimate,
            "permissions": self.permissions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "install_source": self.install_source,
            "tags": self.tags,
        }
