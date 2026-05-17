"""
NEXUS Monitoring — Metrics data models.

Defines the core dataclasses used throughout the monitoring system
for tracking system health, token usage, and tool call performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SystemMetrics:
    """Snapshot of current system state."""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    active_tasks: int = 0
    tokens_used_today: int = 0
    tool_calls_today: int = 0
    errors_last_hour: int = 0
    uptime_seconds: float = 0.0
    agents_running: int = 0
    active_connections: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "active_tasks": self.active_tasks,
            "tokens_used_today": self.tokens_used_today,
            "tool_calls_today": self.tool_calls_today,
            "errors_last_hour": self.errors_last_hour,
            "uptime_seconds": self.uptime_seconds,
            "agents_running": self.agents_running,
            "active_connections": self.active_connections,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TokenUsage:
    """Record of a single LLM token usage event."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    provider: str = ""
    model: str = ""
    tool_name: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "provider": self.provider,
            "model": self.model,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
        }


@dataclass
class ToolCallRecord:
    """Record of a single tool invocation."""

    tool_name: str
    duration_ms: float
    success: bool
    error: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ErrorRecord:
    """Record of a single error event."""

    error_type: str
    details: str
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }
