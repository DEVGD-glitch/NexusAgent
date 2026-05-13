"""
NEXUS API Package — Gateway server, voice routes, and proxy modules.

Primary entry point:
    from nexus.api.gateway import app  # The FastAPI application

Voice API:
    from nexus.api.voice_routes import router  # Voice APIRouter
"""

from nexus.api.gateway import app

__all__ = ["app"]
