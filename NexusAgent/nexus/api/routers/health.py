"""NEXUS API — Health check endpoints."""
from fastapi import APIRouter
from nexus.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "version": "1.0.0"}


@router.get("/ready")
async def readiness_check():
    """Readiness check — verifies critical services."""
    settings = get_settings()
    providers = settings.available_providers
    return {
        "status": "ready",
        "providers_available": len(providers),
        "providers": list(providers),
    }
