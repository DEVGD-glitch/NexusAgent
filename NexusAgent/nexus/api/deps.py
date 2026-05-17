"""NEXUS API — Dependency injection."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Header
from nexus.core.config import get_settings


def get_auth_header(authorization: str | None = Header(None)) -> str | None:
    """Extract Bearer token from Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None
