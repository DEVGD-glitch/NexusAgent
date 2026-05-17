"""NEXUS API — Plugin endpoints."""
from fastapi import APIRouter
from nexus.core.config import get_settings

router = APIRouter()


@router.get("/list")
async def list_plugins():
    """List all plugins."""
    settings = get_settings()
    plugin_dir = settings.plugin_dir if hasattr(settings, 'plugin_dir') else "./nexus_data/plugins"
    return {
        "plugins": [],
        "plugin_dir": plugin_dir,
        "note": "Plugin system requires initialization via PluginEngine"
    }


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str):
    """Enable a plugin."""
    return {"plugin": plugin_id, "status": "enabled", "note": "Requires PluginEngine initialization"}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str):
    """Disable a plugin."""
    return {"plugin": plugin_id, "status": "disabled", "note": "Requires PluginEngine initialization"}
