"""NEXUS API — Tool endpoints."""
from fastapi import APIRouter, HTTPException
from nexus.tools.registry import get_tool_registry

router = APIRouter()


@router.get("/list")
async def list_tools():
    """List all available tools."""
    registry = get_tool_registry()
    tools = registry.list_tools()
    return {"tools": [t.to_dict() for t in tools], "count": len(tools)}


@router.get("/categories")
async def list_categories():
    """List tool categories."""
    registry = get_tool_registry()
    tools = registry.list_tools()
    categories = {}
    for t in tools:
        cat = t.category.value
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1
    return {"categories": categories}


@router.post("/call")
async def call_tool(request: dict):
    """Call a tool by name."""
    tool_name = request.get("tool")
    args = request.get("args", {})
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name required")

    registry = get_tool_registry()
    try:
        result = await registry.execute(tool_name, **args)
        return {"tool": tool_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
