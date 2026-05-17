"""
NEXUS TUI — Agent Monitor Panel

Multi-agent monitoring panel showing active agents, their status,
resource usage, and task progress.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

import httpx
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Label, RichLog, Static

# ═══════════════════════════════════════════════════════════════════════
# Agent Monitor Panel Styles
# ═══════════════════════════════════════════════════════════════════════

AGENTMON_CSS = """
AgentMonitorPanel {
    height: 100%;
}

#agentmon-container {
    height: 100%;
}

#agentmon-header {
    height: 3;
    background: #0f0f1a;
    border-bottom: solid #1e1e32;
    padding: 0 1;
}

#agentmon-header > Horizontal {
    height: 3;
}

#agentmon-title {
    color: #00d4aa;
    text-style: bold;
    width: 1fr;
}

#agentmon-refresh-btn {
    background: #14141f;
    color: #e2e8f0;
    border: solid #1e1e32;
    min-width: 12;
}

#agentmon-refresh-btn:hover {
    background: #1e1e32;
    border: solid #00d4aa;
}

#agentmon-list {
    height: 1fr;
    background: #0a0a0f;
    padding: 1;
    overflow-y: auto;
}

/* Agent card */
.agent-card {
    height: auto;
    background: #14141f;
    border: solid #1e1e32;
    margin: 1 0;
    padding: 1 2;
}

.agent-card-header {
    height: 1;
}

.agent-card-id {
    color: #e2e8f0;
    text-style: bold;
}

.agent-card-type {
    color: #7c3aed;
}

.agent-card-task {
    color: #e2e8f0;
    height: auto;
    padding: 0 1;
}

.agent-card-status {
    height: 1;
}

.agent-status-running {
    color: #22c55e;
}

.agent-status-pending {
    color: #f59e0b;
}

.agent-status-completed {
    color: #64748b;
}

.agent-status-error {
    color: #ef4444;
}

.agent-card-details {
    color: #64748b;
    height: 1;
}

/* Agent types section */
#agentmon-types {
    height: auto;
    background: #0f0f1a;
    border: solid #1e1e32;
    margin: 1;
    padding: 1;
}

.agent-types-title {
    color: #00d4aa;
    text-style: bold;
    height: 1;
    margin: 0 0 1 0;
}

.agent-type-badge {
    padding: 0 1;
    margin: 0 1 0 0;
}

#agentmon-empty {
    height: 100%;
    content-align: center middle;
    color: #64748b;
    text-style: italic;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Agent Card Widget
# ═══════════════════════════════════════════════════════════════════════

class AgentCard(Container):
    """A single agent instance display card."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        task: str = "",
        status: str = "idle",
        created: str = "",
        provider: str = "",
    ) -> None:
        super().__init__()
        self._agent_id = agent_id
        self._agent_type = agent_type
        self._task = task
        self._status = status
        self._created = created
        self._provider = provider
        self.classes = "agent-card"

    def compose(self) -> ComposeResult:
        with Horizontal(classes="agent-card-header"):
            yield Static(
                f"[bold #e2e8f0]Agent:[/] [#00d4aa]{self._agent_id[:16]}[/]  "
                f"[#64748b]|[/]  [bold #7c3aed]{self._agent_type}[/]",
                classes="agent-card-id",
            )
        if self._task:
            yield Static(
                f"[dim]Task:[/] {self._task[:80]}",
                classes="agent-card-task",
            )
        status_style = self._status_class(self._status)
        yield Static(
            f"[{status_style}]● {self._status.upper()}[/]  "
            f"[dim]{self._created}[/]"
            + (f"  |  Provider: {self._provider}" if self._provider else ""),
            classes="agent-card-details",
        )

    @staticmethod
    def _status_class(status: str) -> str:
        """Map status to style class."""
        mapping = {
            "running": "agent-status-running",
            "active": "agent-status-running",
            "idle": "agent-status-running",
            "pending": "agent-status-pending",
            "waiting": "agent-status-pending",
            "completed": "agent-status-completed",
            "done": "agent-status-completed",
            "error": "agent-status-error",
            "failed": "agent-status-error",
        }
        return mapping.get(status.lower(), "agent-status-pending")


# ═══════════════════════════════════════════════════════════════════════
# Agent Monitor Panel
# ═══════════════════════════════════════════════════════════════════════

class AgentMonitorPanel(Container):
    """Multi-agent monitoring panel."""

    CSS = AGENTMON_CSS

    agent_count: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self._poll_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="agentmon-container"):
            with Container(id="agentmon-header"):
                with Horizontal():
                    yield Label(
                        "Agent Monitor", id="agentmon-title"
                    )
                    yield Button("🔄 Refresh Agents", id="agentmon-refresh-btn")
            yield VerticalScroll(id="agentmon-list")
            yield Static(id="agentmon-types")

    def on_mount(self) -> None:
        """Start polling agents."""
        self._show_loading()
        self._poll_task = asyncio.create_task(self._poll_agents())

    def _show_loading(self) -> None:
        """Show loading state."""
        agent_list = self.query_one("#agentmon-list", VerticalScroll)
        agent_list.mount(
            Static(
                "[dim #64748b]Connecting to NEXUS backend...[/]",
                id="agentmon-empty",
            )
        )

    async def _poll_agents(self) -> None:
        """Poll backend for agent info."""
        while True:
            try:
                async with httpx.AsyncClient(
                    base_url="http://127.0.0.1:8081", timeout=5.0
                ) as client:
                    # Get agent list
                    resp = await client.get("/agents/list")
                    if resp.status_code == 200:
                        data = resp.json()
                        self._display_agents(data)
                    else:
                        self._show_empty("No agent data available")

                    # Get capabilities for agent types
                    cap_resp = await client.get("/capabilities")
                    if cap_resp.status_code == 200:
                        cap_data = cap_resp.json()
                        self._display_agent_types(cap_data.get("agent_types", []))

            except httpx.ConnectError:
                self._show_empty(
                    "Cannot connect to NEXUS backend.\n"
                    "Start the server with: nexus serve"
                )
            except Exception as exc:
                self._show_empty(f"Error: {exc}")

            await asyncio.sleep(5.0)

    def _display_agents(self, data: dict) -> None:
        """Display agent instances."""
        agent_list = self.query_one("#agentmon-list", VerticalScroll)
        agent_list.remove_children()

        stats = data.get("stats", {})
        instances = stats.get("instances", [])

        if not instances:
            # Show types as available agents
            types = data.get("types", [])
            if types:
                for t in types:
                    if isinstance(t, dict):
                        agent_type = t.get("type", str(t))
                        status = t.get("status", "available")
                    else:
                        agent_type = str(t)
                        status = "available"

                    card = AgentCard(
                        agent_id=f"{agent_type}-default",
                        agent_type=agent_type,
                        status=status,
                    )
                    agent_list.mount(card)
            else:
                agent_list.mount(
                    Static(
                        "[dim #64748b]No agents available. "
                        "Spawn an agent with /agents spawn[/]",
                    )
                )
            self.agent_count = len(agent_list.children)
            return

        for inst in instances:
            if isinstance(inst, dict):
                card = AgentCard(
                    agent_id=inst.get("agent_id", inst.get("id", "—")),
                    agent_type=inst.get("agent_type", inst.get("type", "general")),
                    task=inst.get("task", ""),
                    status=inst.get("status", "idle"),
                    created=inst.get("created_at", ""),
                    provider=inst.get("provider", ""),
                )
                agent_list.mount(card)

        self.agent_count = len(agent_list.children)

    def _display_agent_types(self, types: list) -> None:
        """Display available agent types."""
        types_section = self.query_one("#agentmon-types", Static)
        if types:
            badges = "  ".join(
                f"[bold #7c3aed]◈ {t}[/]"
                for t in types
            )
            types_section.update(
                f"[bold #00d4aa]Available Agent Types[/]\n{badges}"
            )
        else:
            types_section.update(
                "[dim #64748b]Agent type information not available[/]"
            )

    def _show_empty(self, message: str) -> None:
        """Show empty state message."""
        try:
            agent_list = self.query_one("#agentmon-list", VerticalScroll)
            agent_list.remove_children()
            agent_list.mount(
                Static(f"[dim #64748b]{message}[/]", id="agentmon-empty")
            )
            self.agent_count = 0
        except Exception:
            pass

    @on(Button.Pressed, "#agentmon-refresh-btn")
    async def on_refresh(self) -> None:
        """Manually refresh agents."""
        self._show_empty("Refreshing...")
        await self._poll_agents()
        self.app.notify("Agent list refreshed", timeout=2)

    async def refresh_data(self) -> None:
        """Refresh on external request."""
        await self._poll_agents()
