"""
NEXUS Observability — Evaluation, tracing, and monitoring.

Integrates with:
  - OpenTelemetry for distributed tracing
  - Langfuse for LLM observability (optional)
  - Built-in metrics collection
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A tracing span for an operation."""
    name: str
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    parent_id: Optional[str] = None
    span_id: str = ""

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.monotonic()
        return (end - self.start_time) * 1000


MAX_SPANS = 1000
MAX_LLM_CALLS = 500
MAX_METRICS_PER_NAME = 1000


class ObservabilityManager:
    """
    Central observability manager for NEXUS.

    Provides:
      - Distributed tracing (OpenTelemetry compatible)
      - LLM call tracing
      - Metrics collection
      - Optional Langfuse integration

    Usage:
        obs = ObservabilityManager()
        with obs.trace("task_execution") as span:
            span.set_attribute("task", "research")
            # ... do work ...
    """

    def __init__(self):
        self.settings = get_settings()
        self._spans: list[Span] = []
        self._metrics: dict[str, list[float]] = {}
        self._llm_calls: list[dict[str, Any]] = []

    def trace(self, name: str, attributes: Optional[dict[str, Any]] = None) -> "Tracer":
        """Create a new tracing span."""
        span = Span(name=name, attributes=attributes or {})
        return Tracer(span, self)

    def record_llm_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        cost_usd: float = 0.0,
        success: bool = True,
    ):
        """Record an LLM API call for observability."""
        self._llm_calls.append({
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "success": success,
            "timestamp": time.time(),
        })
        # Prune old LLM calls to prevent memory leak
        if len(self._llm_calls) > MAX_LLM_CALLS:
            self._llm_calls = self._llm_calls[-MAX_LLM_CALLS:]

    def record_metric(self, name: str, value: float):
        """Record a custom metric."""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
        # Prune old metrics to prevent memory leak
        if len(self._metrics[name]) > MAX_METRICS_PER_NAME:
            self._metrics[name] = self._metrics[name][-MAX_METRICS_PER_NAME:]

    def get_stats(self) -> dict[str, Any]:
        """Get observability statistics."""
        total_llm_calls = len(self._llm_calls)
        total_tokens = sum(
            c.get("prompt_tokens", 0) + c.get("completion_tokens", 0)
            for c in self._llm_calls
        )
        total_cost = sum(c.get("cost_usd", 0) for c in self._llm_calls)
        avg_latency = (
            sum(c["latency_ms"] for c in self._llm_calls) / total_llm_calls
            if total_llm_calls > 0 else 0
        )

        return {
            "total_llm_calls": total_llm_calls,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_llm_latency_ms": round(avg_latency, 2),
            "active_spans": len(self._spans),
            "custom_metrics": {k: {"count": len(v), "avg": sum(v) / len(v) if v else 0}
                               for k, v in self._metrics.items()},
        }


class Tracer:
    """Context manager for tracing spans."""

    def __init__(self, span: Span, manager: ObservabilityManager):
        self.span = span
        self.manager = manager

    def __enter__(self) -> "Tracer":
        self.manager._spans.append(self.span)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span.end_time = time.monotonic()
        if exc_type:
            self.span.status = "error"
            self.span.attributes["error"] = str(exc_val)
        # Prune old spans to prevent memory leak
        if len(self.manager._spans) > MAX_SPANS:
            self.manager._spans = self.manager._spans[-MAX_SPANS:]

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.span.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None):
        """Add an event to the span."""
        if "events" not in self.span.attributes:
            self.span.attributes["events"] = []
        self.span.attributes["events"].append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })


# Global observability singleton
_observability: Optional[ObservabilityManager] = None
_observability_lock = threading.Lock()


def get_observability() -> ObservabilityManager:
    """Get the global ObservabilityManager singleton.

    Thread-safe: uses double-checked locking to ensure
    the singleton is created exactly once under concurrent access.
    """
    global _observability
    if _observability is None:
        with _observability_lock:
            if _observability is None:
                _observability = ObservabilityManager()
    return _observability
