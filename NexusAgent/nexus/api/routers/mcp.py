"""NEXUS API — MCP endpoints."""
from fastapi import APIRouter
from nexus.mcp.registry import MCPRegistry

router = APIRouter()


def _get_registry() -> MCPRegistry:
    return MCPRegistry.get_instance()


@router.get("/list")
async def list_mcp_servers():
    """List MCP servers."""
    registry = _get_registry()
    servers = registry.list_mcp()
    return {"servers": [s.to_dict() for s in servers], "count": len(servers)}


@router.get("/tools")
async def list_mcp_tools():
    """List tools from all MCP servers."""
    registry = _get_registry()
    servers = registry.get_enabled()
    tools = []
    for s in servers:
        tools.extend(s.tools or [])
    return {"tools": tools}


@router.post("/{server_id}/toggle")
async def toggle_mcp_server(server_id: str):
    """Enable or disable an MCP server."""
    registry = _get_registry()
    mcp = registry.get(server_id)
    if mcp is None:
        return {"error": f"MCP server '{server_id}' not found"}
    if mcp.status.value == "enabled":
        registry.disable(server_id)
        return {"server": server_id, "status": "disabled"}
    else:
        registry.enable(server_id)
        return {"server": server_id, "status": "enabled"}
