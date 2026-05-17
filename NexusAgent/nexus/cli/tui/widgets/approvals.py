"""Approvals Panel — Pending approval requests queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog, Button
from textual.binding import Binding
from textual.message import Message


@dataclass
class ApprovalRequest:
    id: str
    description: str
    source: str
    created_at: datetime
    details: str = ""


class ApprovalsPanel(Vertical):
    """Panel showing pending approval requests."""

    BINDINGS = [
        Binding("a", "approve", "Approve"),
        Binding("d", "deny", "Deny"),
        Binding("s", "skip", "Skip"),
    ]

    class Approved(Message):
        def __init__(self, request_id: str) -> None:
            self.request_id = request_id
            super().__init__()

    class Denied(Message):
        def __init__(self, request_id: str) -> None:
            self.request_id = request_id
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._queue: list[ApprovalRequest] = []
        self._current_index: int = 0

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Approvals[/] — [dim]a:Approve d:Deny s:Skip[/]",
            id="approvals-header",
        )
        yield RichLog(
            id="approvals-log",
            wrap=True,
            highlight=True,
            markup=True,
        )
        yield Static("[dim]No pending approvals[/]", id="approvals-current")

    def add_request(self, request: ApprovalRequest) -> None:
        self._queue.append(request)
        log = self.query_one("#approvals-log", RichLog)
        log.write(
            f"[yellow]NEW[/] [{request.id}] {request.description}\n"
            f"  Source: {request.source} | {request.created_at:%H:%M:%S}"
        )
        self._update_display()

    def _update_display(self) -> None:
        current = self.query_one("#approvals-current", Static)
        if not self._queue:
            current.update("[dim]No pending approvals[/]")
            return
        if self._current_index >= len(self._queue):
            self._current_index = 0
        req = self._queue[self._current_index]
        current.update(
            f"[bold]#{self._current_index + 1}/{len(self._queue)}[/] "
            f"[{req.id}] {req.description}\n"
            f"  [dim]{req.details}[/]"
        )

    def action_approve(self) -> None:
        if not self._queue:
            return
        req = self._queue.pop(self._current_index)
        log = self.query_one("#approvals-log", RichLog)
        log.write(f"[green]APPROVED[/] [{req.id}] {req.description}")
        self.post_message(ApprovalsPanel.Approved(req.id))
        if self._current_index >= len(self._queue):
            self._current_index = max(0, len(self._queue) - 1)
        self._update_display()

    def action_deny(self) -> None:
        if not self._queue:
            return
        req = self._queue.pop(self._current_index)
        log = self.query_one("#approvals-log", RichLog)
        log.write(f"[red]DENIED[/] [{req.id}] {req.description}")
        self.post_message(ApprovalsPanel.Denied(req.id))
        if self._current_index >= len(self._queue):
            self._current_index = max(0, len(self._queue) - 1)
        self._update_display()

    def action_skip(self) -> None:
        if not self._queue:
            return
        self._current_index = (self._current_index + 1) % len(self._queue)
        self._update_display()
