"""
NEXUS MCP Marketplace Package.

MCPs (Model Context Protocol servers) are **external services** that
require network access. They are managed separately from local tools.

Separation principle:
  - ``nexus.tools``  → local execution (no network)
  - ``nexus.mcp``    → external services (need network)

Public API
----------
* ``MCPDefinition``      – descriptor for an external MCP server
* ``MCPStatus``          – lifecycle status enum
* ``MCPTrustLevel``      – trust / safety level enum
* ``MCPRegistry``        – thread-safe singleton registry
* ``MCPMarketplace``     – discovery & install orchestration
* ``get_mcp_registry()`` – convenience accessor
* ``router``             – FastAPI APIRouter for REST endpoints
"""

from nexus.mcp.models import MCPDefinition, MCPStatus, MCPTrustLevel
from nexus.mcp.registry import (
    MCPNotFoundError,
    MCPRegistry,
    MCPRegistryError,
    get_mcp_registry,
)
from nexus.mcp.marketplace import MCPMarketplace

__all__ = [
    "MCPDefinition",
    "MCPStatus",
    "MCPTrustLevel",
    "MCPRegistry",
    "MCPRegistryError",
    "MCPNotFoundError",
    "MCPMarketplace",
    "get_mcp_registry",
]
