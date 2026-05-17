"""
NEXUS Modes API — FastAPI router for querying and switching agent modes.

Endpoints:
  GET  /api/modes        — List all available modes with their configs
  GET  /api/modes/current — Get current mode and its active configuration
  POST /api/modes/set    — Switch to a different operational mode

All endpoints return JSON.  The router is designed to be mounted on the
main FastAPI gateway application:

    from nexus.modes.api import router as modes_router
    app.include_router(modes_router)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nexus.modes import AgentMode, ModeConfig, get_mode_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modes", tags=["modes"])


# ═══════════════════════════════════════════════════════════════════
# Pydantic request / response models
# ═══════════════════════════════════════════════════════════════════


class ModeInfo(BaseModel):
    """Information about a single operational mode."""

    name: str = Field(..., description="Mode identifier (safe, balanced, auto, sandbox)")
    description: str = Field(..., description="Human-readable description")
    require_confirmation: bool = Field(..., description="Whether every action needs confirmation")
    require_human_approval: list[str] = Field(
        ..., description="Tool names requiring explicit approval, or [\"*\"] for all"
    )
    max_concurrent_tools: int = Field(..., description="Maximum parallel tool executions")
    allow_network: bool = Field(..., description="Whether outbound network is permitted")
    allow_file_write: bool = Field(..., description="Whether file creation is permitted")
    allow_file_delete: bool = Field(..., description="Whether file deletion is permitted")
    allow_code_exec: bool = Field(..., description="Whether code execution is permitted")
    allow_browser: bool = Field(..., description="Whether browser automation is permitted")
    allow_agent_spawn: bool = Field(..., description="Whether agent spawning is permitted")
    log_level: str = Field(..., description="Current Python log level")
    audit_level: str = Field(..., description="Current audit verbosity level")
    max_tokens_per_call: int = Field(..., description="Max LLM tokens per inference call")
    timeout_seconds: int = Field(..., description="Max wall-clock time per operation (s)")
    is_current: bool = Field(default=False, description="Whether this mode is currently active")


class SetModeRequest(BaseModel):
    """Request body for POST /api/modes/set."""

    mode: str = Field(
        ...,
        description="Target mode name",
        examples=["safe", "balanced", "auto", "sandbox"],
        pattern=r"^(safe|balanced|auto|sandbox)$",
    )


class SetModeResponse(BaseModel):
    """Response after a successful mode change."""

    success: bool = Field(default=True, description="Whether the switch succeeded")
    previous_mode: str | None = Field(None, description="The mode that was active before the switch")
    current_mode: str = Field(..., description="The newly active mode")
    description: str = Field(..., description="Human-readable description of the new mode")
    config: dict[str, Any] = Field(default_factory=dict, description="Full active configuration")


class CurrentModeResponse(BaseModel):
    """Response for GET /api/modes/current."""

    current_mode: str = Field(..., description="Currently active mode")
    config: dict[str, Any] = Field(..., description="Full active configuration")


class ListModesResponse(BaseModel):
    """Response for GET /api/modes."""

    modes: list[ModeInfo] = Field(..., description="All available modes")
    current_mode: str = Field(..., description="Currently active mode identifier")


# ═══════════════════════════════════════════════════════════════════
# Lazy singleton accessor
# ═══════════════════════════════════════════════════════════════════


def _get_engine():
    """Lazy-load the ModeEngine singleton."""
    return get_mode_engine()


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=ListModesResponse)
async def list_modes():
    """List all available operational modes with their configurations.

    Returns an array of mode objects, each containing the full
    ``ModeConfig`` plus an ``is_current`` flag indicating whether
    that mode is active.  Also returns the ``current_mode`` string
    at the top level for convenience.
    """
    try:
        engine = _get_engine()
        modes_data = engine.list_modes()
        current = engine.get_current_mode()

        return ListModesResponse(
            modes=[ModeInfo(**m) for m in modes_data],
            current_mode=current.value,
        )

    except Exception as exc:
        logger.error("[ModesAPI] Failed to list modes: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list modes: {str(exc)[:500]}",
        )


@router.get("/current", response_model=CurrentModeResponse)
async def get_current_mode():
    """Get the currently active mode and its full configuration.

    Returns the mode identifier and the complete ``ModeConfig`` dict
    that is currently governing agent behaviour.
    """
    try:
        engine = _get_engine()
        mode = engine.get_current_mode()
        config = engine.get_config()

        return CurrentModeResponse(
            current_mode=mode.value,
            config=config.to_dict(),
        )

    except Exception as exc:
        logger.error("[ModesAPI] Failed to get current mode: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get current mode: {str(exc)[:500]}",
        )


@router.post("/set", response_model=SetModeResponse)
async def set_mode(request: SetModeRequest):
    """Switch the agent to a different operational mode.

    Accepts a JSON body with a ``mode`` field containing one of:
    ``"safe"``, ``"balanced"``, ``"auto"``, or ``"sandbox"``.

    On success, the mode is switched atomically, an event is broadcast
    to all WebSocket subscribers, and the new configuration is returned.
    """
    try:
        # Resolve the target mode from the request
        try:
            target_mode = AgentMode(request.mode)
        except ValueError:
            valid = [m.value for m in AgentMode]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{request.mode}'. Must be one of: {valid}",
            )

        engine = _get_engine()
        old_mode = engine.get_current_mode()
        new_config = engine.set_mode(target_mode)

        logger.info(
            "[ModesAPI] Mode switched via API: %s → %s",
            old_mode.value,
            target_mode.value,
        )

        return SetModeResponse(
            success=True,
            previous_mode=old_mode.value,
            current_mode=target_mode.value,
            description=new_config.description,
            config=new_config.to_dict(),
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("[ModesAPI] Failed to set mode: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set mode: {str(exc)[:500]}",
        )
