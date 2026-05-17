"""
NEXUS MCP Marketplace — FastAPI REST router.

Exposes the MCP registry and local tool registry via HTTP endpoints.
Designed to be mounted on the main NEXUS FastAPI gateway.

Endpoints
---------
MCP endpoints (``/api/mcp/*``):
  * ``GET  /api/mcp``              — list all MCPs
  * ``GET  /api/mcp/{mcp_id}``     — get MCP details
  * ``POST /api/mcp/install``      — install MCP from URL
  * ``POST /api/mcp/{mcp_id}/enable``  — enable MCP
  * ``POST /api/mcp/{mcp_id}/disable`` — disable MCP
  * ``DELETE /api/mcp/{mcp_id}``   — uninstall MCP
  * ``GET  /api/mcp/search``       — search marketplace
  * ``GET  /api/mcp/builtins``     — list built-in MCPs
  * ``GET  /api/mcp/available``    — list remote available MCPs

Tool endpoints (``/api/tools/*``):
  * ``GET  /api/tools``            — list all local tools
  * ``GET  /api/tools/{name}``     — get tool details
  * ``POST /api/tools/{name}/execute`` — execute a local tool
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from nexus.mcp.marketplace import MCPMarketplace
from nexus.mcp.models import MCPStatus
from nexus.mcp.registry import MCPNotFoundError, MCPRegistryError, get_mcp_registry
from nexus.tools import (
    ToolDisabledError,
    ToolNotFoundError,
    ToolRegistryError,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

# ── Router ──────────────────────────────────────────────────────────

router = APIRouter(prefix="/api", tags=["mcp-marketplace"])

# ── Lazy singletons ────────────────────────────────────────────────

_marketplace: Optional[MCPMarketplace] = None


def _get_marketplace() -> MCPMarketplace:
    global _marketplace
    if _marketplace is None:
        _marketplace = MCPMarketplace()
    return _marketplace


def _get_mcp_registry():
    return get_mcp_registry()


def _get_tool_registry():
    return get_tool_registry()


# ═════════════════════════════════════════════════════════════════════
# MCP ENDPOINTS
# ═════════════════════════════════════════════════════════════════════


@router.get("/mcp", summary="List all MCP servers")
async def list_mcp(
    status: Optional[str] = Query(None, description="Filter by status: enabled, disabled, installed, error"),
):
    """Return all registered MCP servers, optionally filtered by status."""
    registry = _get_mcp_registry()
    status_filter = MCPStatus(status) if status else None
    mcps = registry.list_mcp(status=status_filter)
    return {
        "total": len(mcps),
        "mcps": [m.to_dict() for m in mcps],
    }


@router.get("/mcp/{mcp_id}", summary="Get MCP details")
async def get_mcp(mcp_id: str = Path(..., description="MCP identifier")):
    """Return details for a single MCP server."""
    registry = _get_mcp_registry()
    mcp = registry.get(mcp_id)
    if mcp is None:
        raise HTTPException(status_code=404, detail=f"MCP '{mcp_id}' not found")
    return mcp.to_dict()


@router.post("/mcp/install", summary="Install an MCP server")
async def install_mcp(
    url: str = Query(..., description="URL or package name to install from"),
    source: str = Query("github", description="Install source: github, pip, url"),
):
    """Install an MCP server from a URL or package name."""
    marketplace = _get_marketplace()
    try:
        if source == "url":
            registry = _get_mcp_registry()
            mcp = registry.install_from_url(url)
        else:
            mcp = marketplace.install(mcp_id=url, source=source)
        return {"status": "installed", "mcp": mcp.to_dict()}
    except (MCPRegistryError, Exception) as exc:
        logger.error("MCP install failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/mcp/{mcp_id}/enable", summary="Enable an MCP server")
async def enable_mcp(mcp_id: str = Path(..., description="MCP identifier")):
    """Enable a registered MCP server."""
    registry = _get_mcp_registry()
    try:
        registry.enable(mcp_id)
        return {"status": "enabled", "mcp_id": mcp_id}
    except MCPNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/mcp/{mcp_id}/disable", summary="Disable an MCP server")
async def disable_mcp(mcp_id: str = Path(..., description="MCP identifier")):
    """Disable a registered MCP server."""
    registry = _get_mcp_registry()
    try:
        registry.disable(mcp_id)
        return {"status": "disabled", "mcp_id": mcp_id}
    except MCPNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/mcp/{mcp_id}", summary="Uninstall an MCP server")
async def uninstall_mcp(mcp_id: str = Path(..., description="MCP identifier")):
    """Uninstall and remove an MCP server from the registry."""
    marketplace = _get_marketplace()
    try:
        marketplace.uninstall(mcp_id)
        return {"status": "uninstalled", "mcp_id": mcp_id}
    except MCPNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/mcp/search", summary="Search MCP marketplace")
async def search_mcp(q: str = Query("", description="Search query")):
    """Search registered MCP servers by name, description, or tags."""
    marketplace = _get_marketplace()
    results = marketplace.search(q)
    return {
        "query": q,
        "total": len(results),
        "mcps": [m.to_dict() for m in results],
    }


@router.get("/mcp/builtins", summary="List built-in MCP servers")
async def list_builtins():
    """List all built-in MCP servers that ship with NEXUS."""
    registry = _get_mcp_registry()
    builtins = registry.discover_builtins()
    return {
        "total": len(builtins),
        "builtins": [b.to_dict() for b in builtins],
    }


@router.get("/mcp/available", summary="List available MCPs from remote registry")
async def list_available():
    """Fetch available MCP servers from the remote GitHub registry."""
    marketplace = _get_marketplace()
    try:
        available = marketplace.list_available()
        return {
            "total": len(available),
            "available": available,
        }
    except Exception as exc:
        logger.warning("Failed to list available MCPs: %s", exc)
        # Return builtins as fallback
        registry = _get_mcp_registry()
        builtins = registry.discover_builtins()
        return {
            "total": len(builtins),
            "available": [b.to_dict() for b in builtins],
            "note": "Remote registry unavailable, showing builtins",
        }


# ═════════════════════════════════════════════════════════════════════
# TOOL ENDPOINTS
# ═════════════════════════════════════════════════════════════════════


@router.get("/tools", summary="List all local tools")
async def list_tools():
    """Return all registered local tools."""
    registry = _get_tool_registry()
    tools = registry.list_tools()
    return {
        "total": len(tools),
        "tools": [t.to_dict() for t in tools],
        "stats": registry.stats(),
    }


@router.get("/tools/{name}", summary="Get tool details")
async def get_tool(name: str = Path(..., description="Tool name")):
    """Return details for a single local tool."""
    registry = _get_tool_registry()
    tool = registry.get(name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    return tool.to_dict()


@router.post("/tools/{name}/execute", summary="Execute a local tool")
async def execute_tool(
    name: str = Path(..., description="Tool name"),
    params: dict[str, Any] = {},
):
    """Execute a registered local tool with the given parameters.

    The request body is passed as keyword arguments to the tool handler.
    """
    registry = _get_tool_registry()
    try:
        result = await registry.execute(name, **params)
        return {"tool": name, "result": result}
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ToolDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ToolRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Tool '%s' execution failed: %s", name, exc)
        raise HTTPException(status_code=500, detail=f"Tool '{name}' failed: {exc}")


@router.get("/tools/stats", summary="Tool registry statistics")
async def tool_stats():
    """Return statistics about the local tool registry."""
    registry = _get_tool_registry()
    return registry.stats()
