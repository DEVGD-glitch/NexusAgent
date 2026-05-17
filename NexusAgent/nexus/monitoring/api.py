"""
NEXUS Monitoring — FastAPI REST & SSE endpoints.

Provides the HTTP API surface for the monitoring dashboard:
  - GET /api/monitoring/metrics   — current system snapshot
  - GET /api/monitoring/dashboard — full dashboard payload
  - GET /api/monitoring/stream    — SSE real-time stream
  - GET /api/monitoring/tokens    — token usage statistics
  - GET /api/monitoring/errors    — error records
  - GET /api/monitoring/reset     — admin: reset daily counters
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from nexus.monitoring.collector import get_collector
from nexus.monitoring.dashboard import get_dashboard

logger = logging.getLogger(__name__)

# ── Router ─────────────────────────────────────────────────────────

router = APIRouter(
    prefix="/api/monitoring",
    tags=["monitoring"],
)


def _admin_check(request: Request) -> None:
    """
    Simple admin check for destructive operations.

    In production, replace this with proper authentication middleware.
    Checks for an X-Admin-Key header matching the configured admin key.
    """
    # Allow if no admin key is configured (development mode)
    try:
        from nexus.core.config import get_settings
        settings = get_settings()
        admin_key: Optional[str] = getattr(settings, "admin_api_key", None)
        if admin_key:
            provided = request.headers.get("x-admin-key", "")
            if provided != admin_key:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: valid X-Admin-Key header required",
                )
    except ImportError:
        pass  # No settings module — allow in dev


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """
    Return a snapshot of current system metrics.

    Lightweight endpoint for dashboard widgets or external monitoring
    systems to poll periodically without the full dashboard payload.
    """
    try:
        collector = get_collector()
        metrics = collector.get_current_metrics()
        return {
            "success": True,
            "data": metrics.to_dict(),
        }
    except Exception as exc:
        logger.error("Failed to get metrics: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dashboard")
async def get_dashboard() -> dict[str, Any]:
    """
    Return the full dashboard payload.

    Includes CPU, memory, token usage, tool stats, agent status,
    and recent errors in a single response.
    """
    try:
        service = get_dashboard()
        return {
            "success": True,
            "data": service.get_dashboard_data(),
        }
    except Exception as exc:
        logger.error("Failed to get dashboard: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stream")
async def stream_metrics():
    """
    Server-Sent Events (SSE) endpoint for real-time metrics.

    Emits a JSON payload every 2 seconds:
        data: {"cpu_percent": 23.4, "memory_mb": 512, ...}

    Connect from the browser:
        const evtSource = new EventSource("/api/monitoring/stream");
        evtSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            console.log(data);
        };
    """
    try:
        service = get_dashboard()
        return StreamingResponse(
            service.get_metrics_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:
        logger.error("Failed to start metrics stream: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tokens")
async def get_tokens(
    period: str = Query("today", description="Time period: 'today' or 'all'"),
) -> dict[str, Any]:
    """
    Return token usage statistics.

    Args:
        period: "today" for daily stats (default), "all" for all-time.

    Returns:
        Token usage breakdown by provider and totals.
    """
    if period not in ("today", "all"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be 'today' or 'all'.",
        )
    try:
        collector = get_collector()
        return {
            "success": True,
            "data": collector.get_token_usage(period=period),
        }
    except Exception as exc:
        logger.error("Failed to get token stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tools")
async def get_tools(
    period: str = Query("today", description="Time period: 'today' or 'all'"),
) -> dict[str, Any]:
    """
    Return aggregated tool call statistics.

    Args:
        period: "today" for daily stats (default), "all" for all-time.

    Returns:
        Tool call counts, success/failure rates, and average durations.
    """
    if period not in ("today", "all"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be 'today' or 'all'.",
        )
    try:
        collector = get_collector()
        return {
            "success": True,
            "data": collector.get_tool_stats(period=period),
        }
    except Exception as exc:
        logger.error("Failed to get tool stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/errors")
async def get_errors(
    hours: int = Query(24, description="Look-back window in hours"),
) -> dict[str, Any]:
    """
    Return recent error records.

    Args:
        hours: Number of hours to look back (default 24).

    Returns:
        List of error records with type, message, and timestamp.
    """
    if hours < 1 or hours > 720:
        raise HTTPException(
            status_code=400,
            detail="Hours must be between 1 and 720 (30 days).",
        )
    try:
        service = get_dashboard()
        return {
            "success": True,
            "data": service.get_recent_errors(hours=hours),
        }
    except Exception as exc:
        logger.error("Failed to get errors: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/errors/stats")
async def get_error_stats(
    period: str = Query("today", description="Time period: 'today' or 'all'"),
) -> dict[str, Any]:
    """
    Return error statistics grouped by error type.

    Args:
        period: "today" for daily stats (default), "all" for all-time.

    Returns:
        Error counts per error type.
    """
    if period not in ("today", "all"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be 'today' or 'all'.",
        )
    try:
        collector = get_collector()
        return {
            "success": True,
            "data": collector.get_error_stats(period=period),
        }
    except Exception as exc:
        logger.error("Failed to get error stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reset")
async def reset_counters(request: Request) -> dict[str, Any]:
    """
    Reset all daily monitoring counters.

    Admin-only endpoint. Requires X-Admin-Key header if an admin key
    is configured in the environment.
    """
    _admin_check(request)

    try:
        collector = get_collector()
        collector.reset_daily_counters()
        logger.info("Daily counters reset via API")
        return {
            "success": True,
            "message": "Daily counters reset successfully",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to reset counters: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def monitoring_health() -> dict[str, Any]:
    """
    Health check for the monitoring subsystem.

    Returns collector status and uptime for use by external
    monitoring systems (Prometheus, Datadog, etc.).
    """
    try:
        collector = get_collector()
        status = collector.get_status()
        return {
            "success": True,
            "status": "healthy",
            "collector": status,
        }
    except Exception as exc:
        logger.error("Monitoring health check failed: %s", exc)
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(exc),
        }


@router.get("/report")
async def performance_report(
    days: int = Query(7, description="Number of days for the report"),
) -> dict[str, Any]:
    """
    Generate a performance report for the last N days.

    Args:
        days: Number of days to cover (default 7).

    Returns:
        Performance report with token usage, tool stats, error rates.
    """
    if days < 1 or days > 90:
        raise HTTPException(
            status_code=400,
            detail="Days must be between 1 and 90.",
        )
    try:
        service = get_dashboard()
        return {
            "success": True,
            "data": service.get_performance_report(days=days),
        }
    except Exception as exc:
        logger.error("Failed to generate performance report: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
