"""NEXUS API — MCP endpoints."""
from fastapi import APIRouter
from nexus.mcp.registry import get_mcp_registry

router = APIRouter()


@router.get("/list")
async def list_mcp_servers():
    """List MCP servers."""
    registry = get_mcp_registry()
    return {"servers": registry.list_servers(), "count": registry.count()}


@router.get("/tools")
async def list_mcp_tools():
    """List tools from all MCP servers."""
    registry = get_mcp_registry()
    return {"tools": registry.list_tools()}


@router.post("/{server_id}/toggle")
async def toggle_mcp_server(server_id: str):
    """Enable or disable an MCP server."""
    registry = get_mcp_registry()
    registry.toggle_server(server_id)
    return {"server": server_id, "status": "toggled"}
