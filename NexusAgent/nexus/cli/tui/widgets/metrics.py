"""Metrics Panel — Live system metrics dashboard."""

from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, ProgressBar
from textual.reactive import reactive


class MetricCard(Static):
    """A single metric display card."""

    def __init__(self, label: str, value: str = "—", unit: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._unit = unit

    def compose(self) -> ComposeResult:
        yield Static(f"[dim]{self._label}[/]", classes="metric-label")
        yield Static(f"[bold]{self._value}[/] [dim]{self._unit}[/]", classes="metric-value")

    def update_value(self, value: str, unit: str = "") -> None:
        self._value = value
        self._unit = unit
        value_widget = self.query_one(".metric-value", Static)
        value_widget.update(f"[bold]{value}[/] [dim]{unit}[/]")


class MetricsPanel(Vertical):
    """Live system metrics with auto-refresh."""

    DEFAULT_CSS = """
    MetricsPanel {
        height: 100%;
        overflow-y: auto;
    }
    #metrics-grid {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        padding: 1;
    }
    MetricCard {
        border: solid $primary;
        padding: 0 1;
        height: 4;
    }
    .metric-label {
        color: $text-muted;
    }
    .metric-value {
        color: $accent;
        text-align: center;
    }
    #metrics-agents {
        height: auto;
        max-height: 12;
        overflow-y: auto;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
    }
    """

    _cpu: reactive[float] = reactive(0.0)
    _memory: reactive[float] = reactive(0.0)
    _tokens: reactive[int] = reactive(0)
    _tool_calls: reactive[int] = reactive(0)
    _errors: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static("[bold]System Metrics[/]", id="metrics-header")
        with Horizontal(id="metrics-grid"):
            yield MetricCard("CPU", "0", "%", id="metric-cpu")
            yield MetricCard("Memory", "0", "MB", id="metric-mem")
            yield MetricCard("Tokens Today", "0", "", id="metric-tokens")
            yield MetricCard("Tool Calls", "0", "", id="metric-tools")
            yield MetricCard("Errors (1h)", "0", "", id="metric-errors")
            yield MetricCard("Active Agents", "0", "", id="metric-agents-count")
        yield Static("[bold]Active Agents[/]", id="agents-header")
        yield Static("No active agents", id="metrics-agents")

    def on_mount(self) -> None:
        self.set_interval(2.0, self._refresh)

    async def _refresh(self) -> None:
        try:
            from nexus.monitoring import get_collector
            collector = get_collector()
            metrics = collector.get_system_metrics()

            self.query_one("#metric-cpu", MetricCard).update_value(
                f"{metrics.cpu_percent:.1f}", "%"
            )
            self.query_one("#metric-mem", MetricCard).update_value(
                f"{metrics.memory_mb:.0f}", "MB"
            )
            self.query_one("#metric-tokens", MetricCard).update_value(
                f"{metrics.tokens_used_today:,}", ""
            )
            self.query_one("#metric-tools", MetricCard).update_value(
                f"{metrics.tool_calls_today:,}", ""
            )
            self.query_one("#metric-errors", MetricCard).update_value(
                str(metrics.errors_last_hour), ""
            )
            self.query_one("#metric-agents-count", MetricCard).update_value(
                str(len(metrics.agents_running)), ""
            )

            agents_widget = self.query_one("#metrics-agents", Static)
            if metrics.agents_running:
                lines = []
                for agent in metrics.agents_running:
                    aid = agent.get("id", "?")[:8]
                    atype = agent.get("type", "?")
                    status = agent.get("status", "?")
                    task = agent.get("task", "")[:40]
                    lines.append(f"  [{aid}] {atype} — {status} — {task}")
                agents_widget.update("\n".join(lines))
            else:
                agents_widget.update("No active agents")
        except Exception:
            pass
