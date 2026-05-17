"""
NEXUS Local Tools Package.

Tools are **local-only** operations that execute directly on the host
WITHOUT network access. They represent the safe, air-gapped core of NEXUS.

Separation principle:
  - ``nexus.tools``  → local execution (no network)
  - ``nexus.mcp``    → external services (need network)

Public API
----------
* ``Tool``               – dataclass descriptor for a local tool
* ``ToolCategory``       – enumeration of tool domains
* ``ToolRegistry``       – thread-safe singleton registry
* ``get_tool_registry()`` – convenience accessor
"""

from nexus.tools.base import Tool, ToolCategory
from nexus.tools.registry import (
    ToolDisabledError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistry,
    ToolRegistryError,
    ToolTimeoutError,
    get_tool_registry,
)

# Auto-register sovereign tools on import
_registry = get_tool_registry()
_registry.import_sovereign_tools()

__all__ = [
    "Tool",
    "ToolCategory",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolNotFoundError",
    "ToolDisabledError",
    "ToolExecutionError",
    "ToolTimeoutError",
    "get_tool_registry",
]
