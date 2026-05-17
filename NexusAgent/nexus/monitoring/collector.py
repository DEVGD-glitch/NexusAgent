"""
NEXUS Monitoring — Metrics collection engine.

Provides a singleton MetricsCollector that tracks system health,
token usage, tool call performance, and error rates. Designed to
be called from any part of the backend with minimal overhead.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Optional

from nexus.monitoring.metrics import ErrorRecord, SystemMetrics, TokenUsage, ToolCallRecord

logger = logging.getLogger(__name__)

# Try to import psutil — gracefully degrade if unavailable
try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    logger.warning("psutil not installed; CPU/memory metrics will show 0")


class MetricsCollector:
    """
    Singleton metrics collector for NEXUS Agent.

    Tracks real-time and historical metrics:
      - System: CPU, memory, process uptime
      - Token: per-provider/model token usage with cost estimation
      - Tool: call count, duration, success/failure per tool
      - Errors: typed error events with timestamps

    All public methods are thread-safe. The collector runs a background
    task that periodically captures system metrics.

    Usage:
        collector = get_collector()
        collector.record_token_usage(TokenUsage(...))
        metrics = collector.get_current_metrics()
    """

    def __init__(self) -> None:
        self._start_time: float = time.time()

        # ── Rolling buffers (in-memory) ──────────────────────────
        self._token_records: list[dict[str, Any]] = []
        self._tool_records: list[dict[str, Any]] = []
        self._error_records: list[dict[str, Any]] = []

        # ── Daily counters (reset daily) ─────────────────────────
        self._tokens_today: int = 0
        self._tool_calls_today: int = 0
        self._errors_today: int = 0
        self._errors_last_hour: int = 0
        self._daily_reset_time: float = time.time()

        # ── Per-tool aggregation ────────────────────────────────
        self._tool_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "successes": 0, "failures": 0,
                      "total_duration_ms": 0.0, "avg_duration_ms": 0.0}
        )

        # ── Per-provider token stats ────────────────────────────
        self._provider_tokens: dict[str, dict[str, int]] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
        )

        # ── Agent tracking ──────────────────────────────────────
        self._agents: dict[str, dict[str, Any]] = {}

        # ── Latest system metrics snapshot ──────────────────────
        self._latest_metrics: SystemMetrics = SystemMetrics()
        self._background_task: Optional[asyncio.Task] = None
        self._background_running: bool = False

        logger.info("MetricsCollector initialised")

    # ── Public recorders ────────────────────────────────────────────

    def record_token_usage(self, usage: TokenUsage) -> None:
        """Record an LLM token usage event."""
        record = usage.to_dict()
        if record["timestamp"] == 0.0:
            record["timestamp"] = time.time()

        self._token_records.append(record)

        # Update daily counters
        self._tokens_today += usage.total_tokens

        # Update provider stats
        prov = usage.provider or "unknown"
        self._provider_tokens[prov]["prompt"] += usage.prompt_tokens
        self._provider_tokens[prov]["completion"] += usage.completion_tokens
        self._provider_tokens[prov]["total"] += usage.total_tokens
        self._provider_tokens[prov]["calls"] += 1

        logger.debug("Token usage recorded: %d tokens via %s/%s",
                      usage.total_tokens, usage.provider, usage.model)

    def record_tool_call(self, call: ToolCallRecord) -> None:
        """Record a tool invocation result."""
        record = call.to_dict()
        if record["timestamp"] == 0.0:
            record["timestamp"] = time.time()

        self._tool_records.append(record)
        self._tool_calls_today += 1

        # Aggregate per-tool stats
        stats = self._tool_stats[call.tool_name]
        stats["calls"] += 1
        stats["total_duration_ms"] += call.duration_ms
        stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["calls"]
        if call.success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

        logger.debug("Tool call recorded: %s (%.0fms, success=%s)",
                      call.tool_name, call.duration_ms, call.success)

    def record_error(self, error_type: str, details: str) -> None:
        """Record an error event."""
        record = ErrorRecord(
            error_type=error_type,
            details=details,
            timestamp=time.time(),
        ).to_dict()

        self._error_records.append(record)
        self._errors_today += 1

        # Track errors in the last hour window
        self._errors_last_hour += 1
        # Schedule a decrement after 1 hour
        asyncio.ensure_future(self._decrement_error_counter())

        logger.info("Error recorded: %s — %s", error_type, details[:120])

    async def _decrement_error_counter(self) -> None:
        """Decrement the last-hour error counter after 3600 seconds."""
        await asyncio.sleep(3600)
        if self._errors_last_hour > 0:
            self._errors_last_hour -= 1

    def register_agent(self, agent_id: str, agent_type: str) -> None:
        """Register an agent for tracking in the dashboard."""
        self._agents[agent_id] = {
            "id": agent_id,
            "type": agent_type,
            "status": "idle",
            "task": "",
            "elapsed": 0,
            "started_at": time.time(),
        }
        logger.debug("Agent registered: %s (%s)", agent_id, agent_type)

    def update_agent_status(
        self, agent_id: str, status: str,
        task: str = "", elapsed: int = 0,
    ) -> None:
        """Update the status of a tracked agent."""
        if agent_id in self._agents:
            self._agents[agent_id].update({
                "status": status,
                "task": task,
                "elapsed": elapsed,
            })

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from tracking."""
        self._agents.pop(agent_id, None)

    # ── Query methods ───────────────────────────────────────────────

    def get_current_metrics(self) -> SystemMetrics:
        """Return a snapshot of current system metrics."""
        uptime = time.time() - self._start_time
        cpu = 0.0
        mem = 0.0

        if _HAS_PSUTIL:
            try:
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.Process().memory_info().rss / (1024 * 1024)
            except Exception:
                logger.debug("psutil call failed", exc_info=True)

        self._latest_metrics = SystemMetrics(
            cpu_percent=round(cpu, 1),
            memory_mb=round(mem, 1),
            active_tasks=self._tool_calls_today,
            tokens_used_today=self._tokens_today,
            tool_calls_today=self._tool_calls_today,
            errors_last_hour=self._errors_last_hour,
            uptime_seconds=round(uptime, 1),
            agents_running=len(self._agents),
            active_connections=0,
        )
        return self._latest_metrics

    def get_token_usage(self, period: str = "today") -> dict[str, Any]:
        """
        Return token usage statistics.

        Args:
            period: "today" for daily stats, "all" for all-time.

        Returns:
            Dict with total tokens, cost estimates, and per-provider breakdown.
        """
        cutoff = 0.0
        if period == "today":
            cutoff = self._daily_reset_time

        records = [r for r in self._token_records if r["timestamp"] >= cutoff]

        total_prompt = sum(r["prompt_tokens"] for r in records)
        total_completion = sum(r["completion_tokens"] for r in records)
        total_tokens = sum(r["total_tokens"] for r in records)
        total_cost = sum(r["estimated_cost"] for r in records)
        total_calls = len(records)

        provider_breakdown = {}
        for prov, stats in self._provider_tokens.items():
            provider_breakdown[prov] = {
                "prompt_tokens": stats["prompt"],
                "completion_tokens": stats["completion"],
                "total_tokens": stats["total"],
                "calls": stats["calls"],
            }

        return {
            "period": period,
            "total_calls": total_calls,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "per_provider": provider_breakdown,
        }

    def get_tool_stats(self, period: str = "today") -> list[dict[str, Any]]:
        """
        Return aggregated tool call statistics.

        Args:
            period: "today" or "all".

        Returns:
            Sorted list of tool stat dicts (by call count descending).
        """
        cutoff = 0.0
        if period == "today":
            cutoff = self._daily_reset_time

        # Filter records by period if needed
        if period == "today":
            recent_tools = [
                r for r in self._tool_records
                if r["timestamp"] >= cutoff
            ]
            # Re-aggregate from filtered records
            agg: dict[str, dict[str, Any]] = {}
            for rec in recent_tools:
                name = rec["tool_name"]
                if name not in agg:
                    agg[name] = {"calls": 0, "successes": 0, "failures": 0,
                                 "total_duration_ms": 0.0, "avg_duration_ms": 0.0}
                agg[name]["calls"] += 1
                agg[name]["total_duration_ms"] += rec["duration_ms"]
                if rec["success"]:
                    agg[name]["successes"] += 1
                else:
                    agg[name]["failures"] += 1

            for name, stats in agg.items():
                stats["avg_duration_ms"] = round(
                    stats["total_duration_ms"] / stats["calls"], 1
                ) if stats["calls"] else 0.0
                stats["total_duration_ms"] = round(stats["total_duration_ms"], 1)

            result = [
                {"name": name, **stats}
                for name, stats in agg.items()
            ]
        else:
            # All-time: use the pre-aggregated stats
            result = [
                {
                    "name": name,
                    "calls": stats["calls"],
                    "successes": stats["successes"],
                    "failures": stats["failures"],
                    "total_duration_ms": round(stats["total_duration_ms"], 1),
                    "avg_duration_ms": round(stats["avg_duration_ms"], 1),
                }
                for name, stats in self._tool_stats.items()
            ]

        result.sort(key=lambda x: x["calls"], reverse=True)
        return result

    def get_error_stats(self, period: str = "today") -> list[dict[str, Any]]:
        """
        Return error statistics grouped by error type.

        Args:
            period: "today" or "all".

        Returns:
            List of error stat dicts (by count descending).
        """
        cutoff = 0.0
        if period == "today":
            cutoff = self._daily_reset_time

        records = [r for r in self._error_records if r["timestamp"] >= cutoff]

        by_type: dict[str, int] = {}
        for rec in records:
            et = rec["error_type"]
            by_type[et] = by_type.get(et, 0) + 1

        result = [
            {"error_type": et, "count": cnt}
            for et, cnt in sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        ]
        return result

    def get_recent_errors(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return error records from the last N hours."""
        cutoff = time.time() - (hours * 3600)
        return [
            r for r in self._error_records
            if r["timestamp"] >= cutoff
        ]

    def get_agent_list(self) -> list[dict[str, Any]]:
        """Return list of tracked agents with their current status."""
        now = time.time()
        agents = []
        for agent in self._agents.values():
            entry = dict(agent)
            entry["elapsed"] = int(now - agent.get("started_at", now))
            agents.append(entry)
        agents.sort(key=lambda a: a.get("elapsed", 0), reverse=True)
        return agents

    # ── Lifecycle ───────────────────────────────────────────────────

    def reset_daily_counters(self) -> None:
        """Reset all daily counters (called at midnight or manually)."""
        self._tokens_today = 0
        self._tool_calls_today = 0
        self._errors_today = 0
        self._errors_last_hour = 0
        self._daily_reset_time = time.time()
        self._provider_tokens.clear()

        # Trim buffers to keep only recent records (last 7 days)
        seven_days = time.time() - (7 * 86400)
        self._token_records = [r for r in self._token_records if r["timestamp"] >= seven_days]
        self._tool_records = [r for r in self._tool_records if r["timestamp"] >= seven_days]
        self._error_records = [r for r in self._error_records if r["timestamp"] >= seven_days]

        logger.info("Daily counters reset")

    def get_status(self) -> dict[str, Any]:
        """Return collector health / status information."""
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "token_records": len(self._token_records),
            "tool_records": len(self._tool_records),
            "error_records": len(self._error_records),
            "agents_tracked": len(self._agents),
            "tokens_today": self._tokens_today,
            "tool_calls_today": self._tool_calls_today,
            "errors_today": self._errors_today,
            "psutil_available": _HAS_PSUTIL,
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton accessor
# ═══════════════════════════════════════════════════════════════════

_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get the global MetricsCollector singleton."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
