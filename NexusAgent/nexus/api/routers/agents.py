"""NEXUS API — Agent endpoints."""
from fastapi import APIRouter, HTTPException
from nexus.core.config import get_settings

router = APIRouter()


@router.get("/list")
async def list_agents():
    """List available agent types."""
    return {
        "agents": [
            {"id": "default", "name": "Default Agent", "type": "general"},
            {"id": "coder", "name": "Code Agent", "type": "code"},
            {"id": "researcher", "name": "Research Agent", "type": "research"},
        ]
    }


@router.get("/status")
async def agent_status():
    """Get current agent status."""
    settings = get_settings()
    return {
        "status": "idle",
        "provider": settings.default_provider,
        "model": settings.default_model,
        "mode": "plan",
    }
