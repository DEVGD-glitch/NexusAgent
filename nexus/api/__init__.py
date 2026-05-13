"""
NEXUS API Package — Gateway server and proxy modules.

Primary entry point:
    from nexus.api.gateway import app  # The FastAPI application
"""

from nexus.api.gateway import app

__all__ = ["app"]
