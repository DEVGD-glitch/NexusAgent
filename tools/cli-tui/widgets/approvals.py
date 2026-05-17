"""
NEXUS TUI — Approvals Panel

Pending approval requests queue for tool calls and
sensitive actions that require user confirmation.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

import httpx
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Label, RichLog, Static

# ═══════════════════════════════════════════════════════════════════════
# Approvals Panel Styles
# ═══════════════════════════════════════════════════════════════════════

APPROVALS_CSS = """
ApprovalsPanel {
    height: 100%;
}

#approvals-container {
    height: 100%;
}

#approvals-header {
    height: 3;
    background: #0f0f1a;
    border-bottom: solid #1e1e32;
    padding: 0 1;
    content-align: center middle;
}

#approvals-header-text {
    color: #00d4aa;
    text-style: bold;
}

#approvals-queue {
    height: 1fr;
    background: #0a0a0f;
    padding: 1;
    overflow-y: auto;
}

#approvals-empty {
    height: 100%;
    content-align: center middle;
    color: #64748b;
    text-style: italic;
}

/* Approval card */
.approval-card {
    height: auto;
    background: #14141f;
    border: solid #1e1e32;
    margin: 1 0;
    padding: 1 2;
}

.approval-title {
    color: #f59e0b;
    text-style: bold;
    height: 1;
}

.approval-tool {
    color: #7c3aed;
    height: 1;
}

.approval-args {
    color: #e2e8f0;
    height: auto;
    padding: 0 1;
}

.approval-actions {
    height: 3;
    padding: 1 0;
}

.approval-actions > Button {
    margin: 0 1 0 0;
    min-width: 12;
}

.approval-approve {
    background: #065f46;
    color: #e2e8f0;
    border: solid #22c55e;
}

.approval-approve:hover {
    background: #22c55e;
    color: #0a0a0f;
}

.approval-deny {
    background: #7f1d1d;
    color: #e2e8f0;
    border: solid #ef4444;
}

.approval-deny:hover {
    background: #ef4444;
    color: #0a0a0f;
}

.approval-defer {
    background: #1e1e32;
    color: #e2e8f0;
    border: solid #64748b;
}

.approval-defer:hover {
    background: #64748b;
}

/* Summary */
#approvals-summary {
    height: 3;
    background: #0f0f1a;
    border-top: solid #1e1e32;
    padding: 0 1;
    content-align: center middle;
}

.summary-text {
    color: #64748b;
}

.summary-pending {
    color: #f59e0b;
    text-style: bold;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Approval Card Widget
# ═══════════════════════════════════════════════════════════════════════

class ApprovalCard(Container):
    """A single approval request card."""

    def __init__(
        self,
        req_id: str,
        tool: str,
        args: dict[str, Any],
        timestamp: str = "",
    ) -> None:
        super().__init__()
        self.req_id = req_id
        self._tool = tool
        self._args = args
        self._timestamp = timestamp
        self.classes = "approval-card"

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #f59e0b]⚠ Approval Required[/] [dim #{self.req_id[:8]}[/]",
            id=f"approval-title-{self.req_id}",
            classes="approval-title",
        )
        yield Static(
            f"Tool: [bold #7c3aed]{self._tool}[/]",
            id=f"approval-tool-{self.req_id}",
            classes="approval-tool",
        )
        if self._timestamp:
            yield Static(
                f"[dim]{self._timestamp}[/]",
                id=f"approval-time-{self.req_id}",
                classes="",
            )
        args_text = json.dumps(self._args, indent=2) if self._args else "No arguments"
        yield Static(
            f"[#e2e8f0]{args_text}[/]",
            id=f"approval-args-{self.req_id}",
            classes="approval-args",
        )
        with Horizontal(classes="approval-actions"):
            yield Button("✅ Approve", id=f"appr-{self.req_id}", classes="approval-approve")
            yield Button("❌ Deny", id=f"deny-{self.req_id}", classes="approval-deny")
            yield Button("⏸ Defer", id=f"defer-{self.req_id}", classes="approval-defer")


# ═══════════════════════════════════════════════════════════════════════
# Approvals Panel
# ═══════════════════════════════════════════════════════════════════════

class ApprovalsPanel(Container):
    """Pending approval requests queue."""

    CSS = APPROVALS_CSS

    pending_count: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self._pending: dict[str, ApprovalCard] = {}
        self._approved: list[str] = []
        self._denied: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="approvals-container"):
            with Container(id="approvals-header"):
                yield Label(
                    "Pending Approval Requests",
                    id="approvals-header-text",
                )
            yield VerticalScroll(id="approvals-queue")
            yield Static(id="approvals-summary", classes="summary-text")

    def on_mount(self) -> None:
        """Show empty state."""
        self._update_summary()
        # Add some sample pending requests for demonstration
        self._add_sample_requests()

    def _add_sample_requests(self) -> None:
        """Add sample approval requests to demonstrate the panel."""
        requests = [
            {
                "id": "req_001",
                "tool": "execute_code",
                "args": {"language": "python", "code": "print('hello')"},
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            },
            {
                "id": "req_002",
                "tool": "web_search",
                "args": {"query": "latest AI research papers 2026"},
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            },
            {
                "id": "req_003",
                "tool": "write_file",
                "args": {"path": "/tmp/test.txt", "content": "test data"},
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            },
        ]

        for req in requests:
            self._add_request(
                req["id"], req["tool"], req["args"], req["timestamp"]
            )

    def _add_request(
        self,
        req_id: str,
        tool: str,
        args: dict[str, Any],
        timestamp: str = "",
    ) -> None:
        """Add an approval request to the queue."""
        queue = self.query_one("#approvals-queue", VerticalScroll)
        card = ApprovalCard(req_id, tool, args, timestamp)
        queue.mount(card)
        self._pending[req_id] = card
        self.pending_count = len(self._pending)
        self._update_summary()

    def _remove_request(self, req_id: str) -> None:
        """Remove an approval request from the queue."""
        card = self._pending.pop(req_id, None)
        if card:
            card.remove()
            self.pending_count = len(self._pending)
            self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary bar."""
        summary = self.query_one("#approvals-summary", Static)
        pending = len(self._pending)
        approved = len(self._approved)
        denied = len(self._denied)

        summary_text = (
            f"[#f59e0b]{pending} pending[/]  |  "
            f"[#22c55e]{approved} approved[/]  |  "
            f"[#ef4444]{denied} denied[/]"
        )
        summary.update(summary_text)

    @on(Button.Pressed)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle approve/deny/defer button clicks."""
        btn_id = event.button.id or ""

        if btn_id.startswith("appr-"):
            req_id = btn_id[5:]
            self._approved.append(req_id)
            self._remove_request(req_id)
            self.app.notify(f"Approved request #{req_id[:8]}", timeout=2)

        elif btn_id.startswith("deny-"):
            req_id = btn_id[5:]
            self._denied.append(req_id)
            self._remove_request(req_id)
            self.app.notify(f"Denied request #{req_id[:8]}", timeout=2)

        elif btn_id.startswith("defer-"):
            req_id = btn_id[6:]
            self.app.notify(f"Deferred request #{req_id[:8]}", timeout=2)

    async def refresh_data(self) -> None:
        """Refresh the approvals panel."""
        pass
