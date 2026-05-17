"""
NEXUS TUI — Metrics Panel

Live metrics display showing CPU, memory, token usage, and
NEXUS backend health information.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import httpx
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static

# ═══════════════════════════════════════════════════════════════════════
# Metrics Panel Styles
# ═══════════════════════════════════════════════════════════════════════

METRICS_CSS = """
MetricsPanel {
    height: 100%;
}

#metrics-container {
    height: 100%;
    padding: 1;
}

/* Metric card */
.metric-card {
    width: 1fr;
    height: 5;
    background: #14141f;
    border: solid #1e1e32;
    padding: 1 2;
    margin: 1;
}

.metric-card-title {
    color: #64748b;
    text-style: bold;
    text-size: small;
    height: 1;
}

.metric-card-value {
    color: #00d4aa;
    text-style: bold;
    text-size: large;
    height: 2;
}

.metric-card-subtitle {
    color: #64748b;
    text-size: small;
    height: 1;
}

.metric-card.health-card {
    border: solid #22c55e;
}

.metric-card.health-card.warning {
    border: solid #f59e0b;
}

.metric-card.health-card.critical {
    border: solid #ef4444;
}

/* Layout grids */
#metrics-top-row {
    height: 12;
}

#metrics-bottom-row {
    height: 12;
}

.metrics-column {
    width: 1fr;
}

/* Details panel */
#metrics-details {
    height: 1fr;
    background: #0f0f1a;
    border: solid #1e1e32;
    margin: 1;
    padding: 1;
    overflow-y: auto;
}

#metrics-details-title {
    color: #00d4aa;
    text-style: bold;
    height: 1;
    margin: 0 0 1 0;
}

.details-row {
    color: #e2e8f0;
    height: 1;
}

.details-key {
    color: #64748b;
}

.details-value {
    color: #e2e8f0;
}

.details-value.online {
    color: #22c55e;
}

.details-value.offline {
    color: #ef4444;
}

/* Status indicator */
#metrics-status-line {
    height: 3;
    background: #0f0f1a;
    border: solid #1e1e32;
    margin: 1;
    padding: 1;
    content-align: center middle;
}

.metrics-uptime {
    color: #64748b;
}

.metrics-version {
    color: #00d4aa;
    text-style: bold;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Metric Card Widget
# ═══════════════════════════════════════════════════════════════════════

class MetricCard(Container):
    """A single metric display card."""

    def __init__(
        self,
        title: str,
        value: str = "—",
        subtitle: str = "",
        health: str = "ok",
    ) -> None:
        super().__init__()
        self._metric_title = title
        self._metric_value = value
        self._metric_subtitle = subtitle
        self._health = health

    def compose(self) -> ComposeResult:
        yield Label(self._metric_title, id="metric-title", classes="metric-card-title")
        yield Label(self._metric_value, id="metric-value", classes="metric-card-value")
        yield Label(self._metric_subtitle, id="metric-subtitle", classes="metric-card-subtitle")

    def update_value(self, value: str, subtitle: str = "", health: str = "ok") -> None:
        """Update the metric value."""
        self._metric_value = value
        if subtitle:
            self._metric_subtitle = subtitle
        self._health = health

        try:
            self.query_one("#metric-value", Label).update(value)
            if subtitle:
                self.query_one("#metric-subtitle", Label).update(subtitle)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# Metrics Panel
# ═══════════════════════════════════════════════════════════════════════

class MetricsPanel(Container):
    """Live metrics display panel."""

    CSS = METRICS_CSS

    def __init__(self) -> None:
        super().__init__()
        self._poll_task: asyncio.Task | None = None
        self._backend_available = False

    def compose(self) -> ComposeResult:
        with Vertical(id="metrics-container"):
            with Horizontal(id="metrics-top-row"):
                with Vertical(id="metrics-col-left", classes="metrics-column"):
                    yield MetricCard("CPU Usage", "—", "waiting...", id="metric-cpu")
                    yield MetricCard("Disk Usage", "—", "waiting...", id="metric-disk")
                with Vertical(id="metrics-col-right", classes="metrics-column"):
                    yield MetricCard("Memory Usage", "—", "waiting...", id="metric-memory")
                    yield MetricCard("Providers", "—", "waiting...", id="metric-providers")
            with Horizontal(id="metrics-bottom-row"):
                with Vertical(classes="metrics-column"):
                    yield MetricCard("Memory Docs", "—", "waiting...", id="metric-memory-docs")
                    yield MetricCard("Skills", "—", "waiting...", id="metric-skills")
                with Vertical(classes="metrics-column"):
                    yield MetricCard("Active Tools", "—", "waiting...", id="metric-tools")
                    yield MetricCard("Agents", "—", "waiting...", id="metric-agents")
            yield Static(id="metrics-status-line")
            yield Static(id="metrics-details")

    def on_mount(self) -> None:
        """Start metrics polling."""
        self._poll_task = asyncio.create_task(self._poll_metrics())

    async def _poll_metrics(self) -> None:
        """Poll the NEXUS backend for metrics every 2 seconds."""
        while True:
            try:
                async with httpx.AsyncClient(
                    base_url="http://127.0.0.1:8081", timeout=5.0
                ) as client:
                    # Get health data
                    resp = await client.get("/health")
                    if resp.status_code == 200:
                        data = resp.json()
                        self._update_metrics(data)
                        self._backend_available = True
                    else:
                        self._set_offline()

                    # Get capabilities/tools/providers
                    cap_resp = await client.get("/capabilities")
                    if cap_resp.status_code == 200:
                        cap_data = cap_resp.json()
                        self._update_capabilities(cap_data)

                    # Get status
                    status_resp = await client.get("/status")
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        self._update_status(status_data)

            except httpx.ConnectError:
                self._set_offline()
            except Exception:
                self._set_offline()

            await asyncio.sleep(2.0)

    def _update_metrics(self, data: dict) -> None:
        """Update the metric cards from health data."""
        sys_metrics = data.get("system_metrics", {})
        subsystems = data.get("subsystems", {})

        # CPU
        cpu = sys_metrics.get("cpu_percent", 0)
        cpu_color = "green" if cpu < 50 else "yellow" if cpu < 80 else "red"
        self._update_card("metric-cpu", f"[{cpu_color}]{cpu:.1f}%[/]")

        # Memory
        mem_percent = sys_metrics.get("memory_percent", 0)
        mem_used = sys_metrics.get("memory_used_gb", 0)
        mem_total = sys_metrics.get("memory_total_gb", 0)
        mem_color = "green" if mem_percent < 50 else "yellow" if mem_percent < 80 else "red"
        self._update_card(
            "metric-memory",
            f"[{mem_color}]{mem_percent:.1f}%[/]",
            f"{mem_used:.1f}GB / {mem_total:.1f}GB",
        )

        # Disk
        disk = sys_metrics.get("disk_percent", 0)
        disk_color = "green" if disk < 50 else "yellow" if disk < 80 else "red"
        disk_used = sys_metrics.get("disk_used_gb", 0)
        disk_total = sys_metrics.get("disk_total_gb", 0)
        self._update_card(
            "metric-disk",
            f"[{disk_color}]{disk:.1f}%[/]",
            f"{disk_used:.1f}GB / {disk_total:.1f}GB",
        )

        # Provider counts
        llm = subsystems.get("llm", {})
        providers_count = llm.get("providers_count", 0)
        active_provider = llm.get("active_provider", "none")
        self._update_card(
            "metric-providers",
            f"[#7c3aed]{providers_count}[/]",
            f"active: {active_provider}",
        )

        # Uptime
        uptime = data.get("uptime_seconds", 0)
        uptime_str = self._format_uptime(uptime)
        version = data.get("version", "—")

        status_line = self.query_one("#metrics-status-line", Static)
        status_line.update(
            f"[bold #00d4aa]NEXUS v{version}[/]  |  "
            f"[#64748b]Uptime: {uptime_str}[/]  |  "
            f"[#22c55e]● Healthy[/]"
        )

        # Subsystem status
        details_parts = []
        for name, info in subsystems.items():
            status = info.get("status", "unknown")
            status_dot = "🟢" if status == "healthy" else "🟡" if status == "degraded" else "🔴"
            details_parts.append(f"[#64748b]{name}:[/] {status_dot} {status}")
        details_text = "\n".join(details_parts) if details_parts else "[dim]No subsystem data[/]"

        details = self.query_one("#metrics-details", Static)
        details.update(
            "[bold #00d4aa]Subsystem Status[/]\n" + details_text
        )

    def _update_capabilities(self, data: dict) -> None:
        """Update capability-related metrics."""
        tool_count = data.get("tool_count", 0)
        skill_count = data.get("skill_count", 0)
        memory_stats = data.get("memory_stats", {})
        agent_types = data.get("agent_types", [])

        self._update_card("metric-tools", f"[#00d4aa]{tool_count}[/]")
        self._update_card("metric-skills", f"[#f59e0b]{skill_count}[/]")
        self._update_card("metric-agents", f"[#7c3aed]{len(agent_types)}[/]")

        # Total doc count
        total_docs = sum(
            v for v in memory_stats.values() if isinstance(v, (int, float))
        )
        self._update_card("metric-memory-docs", f"[#22c55e]{total_docs}[/]")

    def _update_status(self, data: dict) -> None:
        """Update status info from status endpoint."""
        # Status already handled by health endpoint
        pass

    def _update_card(self, card_id: str, value: str, subtitle: str = "") -> None:
        """Update a metric card."""
        try:
            card = self.query_one(f"#{card_id}", MetricCard)
            card.update_value(value, subtitle)
        except Exception:
            pass

    def _set_offline(self) -> None:
        """Mark all metrics as offline."""
        self._backend_available = False
        status_line = self.query_one("#metrics-status-line", Static)
        status_line.update(
            "[bold #ef4444]NEXUS Backend Offline[/]  |  "
            "[#64748b]Start server with: nexus serve[/]"
        )
        details = self.query_one("#metrics-details", Static)
        details.update(
            "[bold #ef4444]Cannot connect to NEXUS backend at http://127.0.0.1:8081[/]"
        )

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable form."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "< 1m"

    async def refresh_data(self) -> None:
        """Refresh metrics on demand."""
        await self._poll_metrics()
