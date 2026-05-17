"""NEXUS API — Rules engine endpoints."""
from fastapi import APIRouter
from nexus.rules.engine import get_rules_engine

router = APIRouter()


@router.get("/list")
async def list_rules():
    """List all rules."""
    engine = get_rules_engine()
    return {"rules": engine.list_rules()}


@router.get("/status")
async def rules_status():
    """Get rules engine status."""
    engine = get_rules_engine()
    return engine.get_status()
