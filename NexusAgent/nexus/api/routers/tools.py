"""NEXUS API — Tool endpoints."""
from fastapi import APIRouter, HTTPException
from nexus.tools.registry import get_tool_registry

router = APIRouter()


@router.get("/list")
async def list_tools():
    """List all available tools."""
    registry = get_tool_registry()
    tools = registry.list_tools()
    return {"tools": tools, "count": len(tools)}


@router.get("/categories")
async def list_categories():
    """List tool categories."""
    registry = get_tool_registry()
    return {"categories": registry.get_categories()}


@router.post("/call")
async def call_tool(request: dict):
    """Call a tool by name."""
    tool_name = request.get("tool")
    args = request.get("args", {})
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name required")

    registry = get_tool_registry()
    try:
        result = await registry.call_tool(tool_name, **args)
        return {"tool": tool_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
