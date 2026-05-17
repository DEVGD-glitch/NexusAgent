"""NEXUS API — Plugin endpoints."""
from fastapi import APIRouter
from nexus.plugins.engine import get_plugin_engine

router = APIRouter()


@router.get("/list")
async def list_plugins():
    """List all plugins."""
    engine = get_plugin_engine()
    return {"plugins": engine.get_status()}


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str):
    """Enable a plugin."""
    engine = get_plugin_engine()
    engine.enable_plugin(plugin_id)
    return {"plugin": plugin_id, "status": "enabled"}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str):
    """Disable a plugin."""
    engine = get_plugin_engine()
    engine.disable_plugin(plugin_id)
    return {"plugin": plugin_id, "status": "disabled"}
