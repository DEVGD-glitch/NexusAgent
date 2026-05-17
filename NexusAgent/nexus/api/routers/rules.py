"""NEXUS API — Rules engine endpoints."""
from fastapi import APIRouter
from nexus.core.config import get_settings

router = APIRouter()


@router.get("/list")
async def list_rules():
    """List all rules."""
    settings = get_settings()
    rules_dir = settings.rules_dir if hasattr(settings, 'rules_dir') else "./nexus_data/rules"
    return {"rules": [], "rules_dir": rules_dir, "note": "Rules engine requires initialization"}


@router.get("/status")
async def rules_status():
    """Get rules engine status."""
    return {"status": "initialized", "loaded": 0, "active": 0}
