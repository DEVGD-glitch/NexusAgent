"""
NEXUS Local Tools — Base definitions.

Tools are local-only operations that execute directly on the host
WITHOUT network access. They represent the "safe" core of NEXUS:
file I/O, code execution, git operations, shell commands, and system
introspection.

Separation principle:
  - tools/   = local execution (no network)
  - mcp/     = external services (need network)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

# Type alias for an async tool handler
#   handler(**kwargs) -> str
ToolHandler = Callable[..., Awaitable[str]]


class ToolCategory(str, Enum):
    """Categorisation of local-only tools."""

    FILE = "file"
    CODE = "code"
    GIT = "git"
    SHELL = "shell"
    SYSTEM = "system"


@dataclass
class Tool:
    """Descriptor for a single local tool registration."""

    name: str
    description: str
    category: ToolCategory
    handler: ToolHandler
    requires_approval: bool = False
    timeout_seconds: int = 30
    enabled: bool = True

    # Metadata automatically populated on registration
    created_at: float = field(default_factory=time.time)
    tool_id: str = field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:12]}")
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for API responses (excludes the callable handler)."""
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "requires_approval": self.requires_approval,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "version": self.version,
            "tags": self.tags,
        }
