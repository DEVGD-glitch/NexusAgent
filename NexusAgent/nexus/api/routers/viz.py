"""NEXUS API — Visualization endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/events")
async def get_viz_events():
    """Get recent visualization events."""
    return {"events": []}
