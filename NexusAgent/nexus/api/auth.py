"""
NEXUS Authentication Middleware — FastAPI dependency for API key / JWT auth.

Design:
  - Reads ``NEXUS_API_KEY`` from environment
  - If unset: development mode, all requests pass (logs a warning once)
  - If set: require ``Authorization: Bearer <key>`` header
  - Public endpoints bypass auth entirely
  - WebSocket connections authenticate via ``?token=`` query param
  - Returns structured 401 JSON on failure
"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import Depends, HTTPException, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────

# Endpoints that never require authentication.
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/status",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# Cached runtime state (module-level, computed once).
_api_key: str | None = None
_dev_mode_warning_shown = False


def _get_api_key() -> str | None:
    """Return the configured API key, or None if not set."""
    global _api_key
    if _api_key is None:
        _api_key = os.getenv("NEXUS_API_KEY", "").strip() or None
    return _api_key


def _is_public(path: str) -> bool:
    """Check whether a request path is public (no auth required)."""
    # Exact match or prefix match for paths like /docs/oauth2-redirect
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")


# ── HTTP Dependency ───────────────────────────────────────────────

_security = HTTPBearer(auto_error=False)


async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> None:
    """
    FastAPI dependency that enforces authentication on every HTTP route.

    - Public endpoints are skipped automatically.
    - In dev mode (no NEXUS_API_KEY) all requests pass.
    - In protected mode the ``Authorization: Bearer <key>`` header is required.
    """
    global _dev_mode_warning_shown

    # Always allow public endpoints.
    if _is_public(request.url.path):
        return

    api_key = _get_api_key()

    # Dev mode — no key configured.
    if api_key is None:
        if not _dev_mode_warning_shown:
            logger.warning(
                "NEXUS_API_KEY is not set — running in DEVELOPMENT mode. "
                "Set the environment variable to enable authentication."
            )
            _dev_mode_warning_shown = True
        return

    # Protected mode — validate Bearer token.
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "authentication_required",
                "message": "Missing or invalid Authorization header. "
                           "Expected: Bearer <api_key>",
            },
        )

    token = credentials.credentials
    if not hmac.compare_digest(token, api_key):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_token",
                "message": "The provided API key is invalid.",
            },
        )


# ── WebSocket Auth Helper ────────────────────────────────────────

async def verify_ws_auth(websocket: WebSocket) -> None:
    """
    Authenticate a WebSocket connection via ``?token=`` query parameter.

    Called inside the WebSocket handler (not as a dependency, since
    FastAPI WebSocket dependencies run before ``accept()``).
    """
    global _dev_mode_warning_shown

    api_key = _get_api_key()

    # Dev mode — allow all.
    if api_key is None:
        if not _dev_mode_warning_shown:
            logger.warning(
                "NEXUS_API_KEY is not set — running in DEVELOPMENT mode. "
                "Set the environment variable to enable authentication."
            )
            _dev_mode_warning_shown = True
        return

    # Protected mode — check query param.
    token = websocket.query_params.get("token", "")
    if not token or not hmac.compare_digest(token, api_key):
        await websocket.close(code=4001, reason="Authentication required")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "ws_auth_failed",
                "message": "WebSocket authentication failed. "
                           "Pass ?token=<api_key> as a query parameter.",
            },
        )


def reset_auth_cache() -> None:
    """Reset cached auth state (useful for testing)."""
    global _api_key, _dev_mode_warning_shown
    _api_key = None
    _dev_mode_warning_shown = False
