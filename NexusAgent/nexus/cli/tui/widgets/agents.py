"""Agents Panel — Multi-agent monitoring and management."""

from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.binding import Binding
from textual.message import Message


class AgentsPanel(Vertical):
    """Panel for monitoring and managing spawned agents."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("k", "kill", "Kill"),
        Binding("l", "logs", "Logs"),
    ]

    class AgentAction(Message):
        def __init__(self, action: str, agent_id: str) -> None:
            self.action = action
            self.agent_id = agent_id
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Agents[/] — [dim]r:Refresh k:Kill l:Logs[/]",
            id="agents-header",
        )
        yield DataTable(id="agents-table")
        yield Static("[dim]No agents running[/]", id="agents-detail")

    def on_mount(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.add_columns("ID", "Type", "Status", "Tokens", "Task")
        table.cursor_type = "row"
        self.set_interval(3.0, self._refresh)

    async def _refresh(self) -> None:
        try:
            from nexus.monitoring import get_collector
            collector = get_collector()
            metrics = collector.get_system_metrics()

            table = self.query_one("#agents-table", DataTable)
            table.clear()

            for agent in metrics.agents_running:
                table.add_row(
                    str(agent.get("id", "?"))[:8],
                    str(agent.get("type", "?")),
                    str(agent.get("status", "?")),
                    f"{agent.get('tokens', 0):,}",
                    str(agent.get("task", ""))[:50],
                )

            detail = self.query_one("#agents-detail", Static)
            if not metrics.agents_running:
                detail.update("[dim]No agents running[/]")
            else:
                detail.update(f"[bold]{len(metrics.agents_running)}[/] agent(s) active")
        except Exception:
            pass

    def action_refresh(self) -> None:
        self.run_worker(self._refresh)

    def action_kill(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            agent_id = row[0]
            self.post_message(AgentsPanel.AgentAction("kill", agent_id))
            self.app.notify(f"Kill signal sent to {agent_id}", severity="warning")

    def action_logs(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            agent_id = row[0]
            self.post_message(AgentsPanel.AgentAction("logs", agent_id))
