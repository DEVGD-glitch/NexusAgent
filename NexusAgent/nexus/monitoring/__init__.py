"""
NEXUS Monitoring — Real-time system observability and dashboard.

Provides a complete monitoring system for NEXUS Agent including:
  - Metrics collection (CPU, memory, tokens, tool calls, errors)
  - Dashboard data aggregation with real-time SSE streaming
  - WebSocket event broadcasting on the 'dashboard:metrics' channel
  - REST API endpoints for dashboard widgets and external monitoring

Usage:
    # Collect metrics from anywhere in the backend
    from nexus.monitoring import get_collector
    collector = get_collector()
    collector.record_token_usage(TokenUsage(...))

    # Serve the dashboard API
    from nexus.monitoring.api import router
    app.include_router(router)

    # Dashboard service with SSE streaming
    from nexus.monitoring import get_dashboard
    service = get_dashboard()
    data = service.get_dashboard_data()
"""

from __future__ import annotations

from nexus.monitoring.collector import MetricsCollector, get_collector
from nexus.monitoring.dashboard import DashboardService, get_dashboard
from nexus.monitoring.metrics import SystemMetrics, TokenUsage, ToolCallRecord, ErrorRecord

__all__ = [
    "MetricsCollector",
    "DashboardService",
    "SystemMetrics",
    "TokenUsage",
    "ToolCallRecord",
    "ErrorRecord",
    "get_collector",
    "get_dashboard",
]
