"""
NEXUS Monitoring — Dashboard data service and SSE streaming.

Provides the DashboardService that assembles the full dashboard payload
and streams real-time metrics updates via Server-Sent Events (SSE) and
the EventBroadcaster's WebSocket channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

from nexus.core.events import get_broadcaster
from nexus.monitoring.collector import get_collector
from nexus.monitoring.collector import MetricsCollector
from nexus.monitoring.metrics import SystemMetrics

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Dashboard data assembly and real-time streaming.

    Aggregates metrics from the MetricsCollector into a rich dashboard
    payload and provides:
      - Full dashboard snapshot via get_dashboard_data()
      - SSE stream via get_metrics_stream() (every 2 seconds)
      - WebSocket events on the "dashboard:metrics" channel
      - Historical queries (errors, performance reports)

    Usage:
        service = DashboardService()
        data = service.get_dashboard_data()
        async for payload in service.get_metrics_stream():
            ...
    """

    def __init__(self, collector: Optional[MetricsCollector] = None) -> None:
        self._collector = collector or get_collector()
        self._broadcaster = get_broadcaster()
        self._stream_task: Optional[asyncio.Task] = None

    # ── Payload assembly ─────────────────────────────────────────—-

    def get_dashboard_data(self) -> dict[str, Any]:
        """
        Build and return the full dashboard payload.

        Returns the complete DashboardPayload JSON object with current
        system metrics, agent status, top tools, and recent errors.
        """
        metrics = self._collector.get_current_metrics()
        top_tools = self._collector.get_tool_stats(period="today")[:5]
        recent_errors = self._collector.get_recent_errors(hours=24)[:10]
        agents = self._collector.get_agent_list()

        # Calculate memory percentage
        memory_percent = self._compute_memory_percent(metrics.memory_mb)

        return {
            "cpu_percent": metrics.cpu_percent,
            "memory_mb": metrics.memory_mb,
            "memory_percent": memory_percent,
            "active_tasks": metrics.active_tasks,
            "tokens_today": metrics.tokens_used_today,
            "tool_calls_today": metrics.tool_calls_today,
            "errors_last_hour": metrics.errors_last_hour,
            "uptime_seconds": metrics.uptime_seconds,
            "agents_running": agents,
            "top_tools": [
                {
                    "name": t["name"],
                    "calls": t["calls"],
                    "avg_duration_ms": t.get("avg_duration_ms", 0.0),
                }
                for t in top_tools
            ],
            "recent_errors": [
                {
                    "time": self._format_timestamp(e["timestamp"]),
                    "type": e["error_type"],
                    "message": e["details"][:200],
                }
                for e in recent_errors
            ],
        }

    def _compute_memory_percent(self, memory_mb: float) -> float:
        """Estimate memory usage as a percentage of total system RAM."""
        try:
            import psutil
            total = psutil.virtual_memory().total / (1024 * 1024)
            if total > 0:
                return round((memory_mb / total) * 100, 1)
        except Exception:
            pass
        return 0.0

    def _format_timestamp(self, ts: float) -> str:
        """Format a Unix timestamp to an ISO-8601 string."""
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    # ── SSE streaming ─────────────────────────────────────────────—-

    async def get_metrics_stream(self) -> AsyncGenerator[str, None]:
        """
        Async generator that yields SSE-formatted metrics every 2 seconds.

        Yields SSE data strings:
            data: {"cpu_percent": 23.4, ...}\n\n

        Usage with FastAPI:
            return StreamingResponse(
                service.get_metrics_stream(),
                media_type="text/event-stream",
            )
        """
        while True:
            try:
                payload = self.get_dashboard_data()
                yield f"data: {json.dumps(payload, default=str)}\n\n"
            except Exception as exc:
                logger.error("Metrics stream error: %s", exc)
                yield f"data: {json.dumps({'error': str(exc)}, default=str)}\n\n"

            await asyncio.sleep(2)

    # ── WebSocket broadcast ───────────────────────────────────────—-

    async def broadcast_metrics(self) -> None:
        """Broadcast current dashboard metrics via EventBroadcaster."""
        try:
            payload = self.get_dashboard_data()
            await self._broadcaster.broadcast("dashboard:metrics", payload)
        except Exception as exc:
            logger.error("Metrics broadcast error: %s", exc)

    async def start_periodic_broadcast(self, interval: float = 2.0) -> None:
        """
        Start a background task that broadcasts dashboard metrics
        on the 'dashboard:metrics' WebSocket channel every N seconds.

        Args:
            interval: Seconds between broadcasts (default 2.0).
        """
        if self._stream_task and not self._stream_task.done():
            logger.warning("Periodic broadcast already running")
            return

        async def _loop() -> None:
            logger.info("Periodic metrics broadcast started (interval=%.1fs)", interval)
            while True:
                try:
                    await self.broadcast_metrics()
                except Exception as exc:
                    logger.error("Broadcast loop error: %s", exc)
                await asyncio.sleep(interval)

        self._stream_task = asyncio.create_task(_loop())

    async def stop_periodic_broadcast(self) -> None:
        """Stop the background metrics broadcast task."""
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None
            logger.info("Periodic metrics broadcast stopped")

    # ── Historical queries ────────────────────────────────────────—-

    def get_recent_errors(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        Return error records from the last N hours.

        Args:
            hours: Look-back window (default 24).

        Returns:
            List of error dicts sorted by time descending.
        """
        errors = self._collector.get_recent_errors(hours=hours)
        errors.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
        return [
            {
                "time": self._format_timestamp(e["timestamp"]),
                "type": e["error_type"],
                "message": e["details"][:500],
            }
            for e in errors
        ]

    def get_performance_report(self, days: int = 7) -> dict[str, Any]:
        """
        Generate a performance report covering the last N days.

        Args:
            days: Number of days to cover (default 7).

        Returns:
            Dict with token usage summary, tool performance,
            error rates, and uptime statistics.
        """
        # Token usage (all-time since we keep 7-day buffer)
        token_stats = self._collector.get_token_usage(period="all")
        tool_stats = self._collector.get_tool_stats(period="all")
        error_stats = self._collector.get_error_stats(period="all")

        total_tool_calls = sum(t["calls"] for t in tool_stats)
        total_tool_failures = sum(t.get("failures", 0) for t in tool_stats)
        error_rate = (
            round((total_tool_failures / total_tool_calls) * 100, 2)
            if total_tool_calls > 0 else 0.0
        )

        metrics = self._collector.get_current_metrics()

        # Find top 5 most expensive tools by avg duration
        top_slowest = sorted(
            tool_stats, key=lambda t: t.get("avg_duration_ms", 0), reverse=True
        )[:5]

        return {
            "report_period_days": days,
            "uptime_seconds": metrics.uptime_seconds,
            "token_usage": token_stats,
            "tool_performance": {
                "total_calls": total_tool_calls,
                "total_failures": total_tool_failures,
                "error_rate_percent": error_rate,
                "top_slowest": [
                    {
                        "name": t["name"],
                        "avg_duration_ms": t.get("avg_duration_ms", 0),
                        "calls": t["calls"],
                    }
                    for t in top_slowest
                ],
            },
            "error_breakdown": error_stats,
            "generated_at": self._format_timestamp(time.time()),
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton accessor
# ═══════════════════════════════════════════════════════════════════

_dashboard: Optional[DashboardService] = None


def get_dashboard() -> DashboardService:
    """Get the global DashboardService singleton."""
    global _dashboard
    if _dashboard is None:
        _dashboard = DashboardService()
    return _dashboard
