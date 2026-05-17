"""
NEXUS TUI — Logs Panel

Real-time log viewer that polls the NEXUS audit log and watches
local log files.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, RichLog, Static

# ═══════════════════════════════════════════════════════════════════════
# Logs Panel Styles
# ═══════════════════════════════════════════════════════════════════════

LOGS_CSS = """
LogsPanel {
    height: 100%;
}

#logs-container {
    height: 100%;
}

#logs-controls {
    height: 3;
    background: #0f0f1a;
    border-bottom: solid #1e1e32;
    padding: 0 1;
}

#logs-controls > Button {
    background: #14141f;
    color: #e2e8f0;
    border: solid #1e1e32;
    margin: 0 1 0 0;
    min-width: 10;
}

#logs-controls > Button:hover {
    background: #1e1e32;
    border: solid #00d4aa;
}

#logs-controls > Button.-active {
    background: #00d4aa;
    color: #0a0a0f;
    border: solid #00d4aa;
}

#logs-output {
    height: 1fr;
    background: #0a0a0f;
    border: none;
    padding: 0 1;
}

.log-entry {
    padding: 0;
    margin: 0;
}

.log-timestamp {
    color: #64748b;
}

.log-level-INFO {
    color: #22c55e;
}

.log-level-WARNING {
    color: #f59e0b;
}

.log-level-ERROR {
    color: #ef4444;
}

.log-level-DEBUG {
    color: #64748b;
}

.log-level-CRITICAL {
    color: #ef4444;
    text-style: bold;
}

.log-message {
    color: #e2e8f0;
}

/* Filter input */
#log-filter {
    background: #14141f;
    color: #e2e8f0;
    border: solid #1e1e32;
    height: 3;
}

#log-filter:focus {
    border: solid #00d4aa;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Logs Panel
# ═══════════════════════════════════════════════════════════════════════

class LogsPanel(Container):
    """Real-time log viewer with filtering."""

    CSS = LOGS_CSS

    def __init__(self) -> None:
        super().__init__()
        self._log_entries: list[dict] = []
        self._filter = ""
        self._polling = False
        self._poll_task: asyncio.Task | None = None
        self._auto_scroll = True

    def compose(self) -> ComposeResult:
        with Vertical(id="logs-container"):
            with Horizontal(id="logs-controls"):
                yield Button("⏸ Pause", id="log-pause", variant="default")
                yield Button("🗑 Clear", id="log-clear", variant="default")
                yield Button("🔄 Refresh", id="log-refresh", variant="default")
                yield Input(
                    placeholder="Filter logs...",
                    id="log-filter",
                )
            yield RichLog(id="logs-output", highlight=True, markup=True, max_lines=10000)

    def on_mount(self) -> None:
        """Start polling logs."""
        output = self.query_one("#logs-output", RichLog)
        output.write("[bold #00d4aa]NEXUS Audit Log Viewer[/]")
        output.write(f"[dim]Connected to http://127.0.0.1:8081[/]")
        output.write("")
        self._start_polling()

    def _start_polling(self) -> None:
        """Start the log polling loop."""
        self._polling = True
        self._poll_task = asyncio.create_task(self._poll_logs())

    async def _poll_logs(self) -> None:
        """Poll the audit log endpoint periodically."""
        while self._polling:
            try:
                async with httpx.AsyncClient(
                    base_url="http://127.0.0.1:8081", timeout=5.0
                ) as client:
                    resp = await client.get("/security/audit", params={"limit": 100})
                    if resp.status_code == 200:
                        data = resp.json()
                        entries = data.get("entries", [])
                        self._process_entries(entries)
            except httpx.ConnectError:
                # Backend not available — wait and retry
                pass
            except Exception:
                pass

            await asyncio.sleep(3.0)

    def _process_entries(self, entries: list[dict]) -> None:
        """Process and display audit log entries."""
        output = self.query_one("#logs-output", RichLog)
        new_entries = []

        for entry in entries:
            entry_id = entry.get("id", "") or entry.get("timestamp", "")
            if entry_id and entry_id not in {e.get("id", "") for e in self._log_entries}:
                new_entries.append(entry)

        if new_entries:
            self._log_entries.extend(new_entries)
            # Keep only last 5000
            if len(self._log_entries) > 5000:
                self._log_entries = self._log_entries[-5000:]

            for entry in reversed(new_entries):
                self._display_entry(entry, output)
            if self._auto_scroll:
                output.scroll_end(animate=False)

    def _display_entry(self, entry: dict, output: RichLog) -> None:
        """Format and display a single log entry."""
        ts = entry.get("timestamp", "")
        action = entry.get("action", "—")
        target = entry.get("target", "")
        outcome = entry.get("outcome", "success")
        details = entry.get("details", {})

        # Format timestamp
        if isinstance(ts, str) and len(ts) > 19:
            try:
                dt = datetime.fromisoformat(ts)
                ts = dt.strftime("%H:%M:%S")
            except ValueError:
                ts = ts[:19]

        # Determine level
        level = "INFO" if outcome == "success" else "ERROR" if outcome == "failure" else "WARNING"

        # Build message
        msg = f"{action}"
        if target:
            msg += f" → {target}"

        # Filter
        if self._filter and self._filter.lower() not in msg.lower():
            return

        level_style = f"log-level-{level}"

        output.write(
            f"[#64748b]{ts}[/] "
            f"[{level_style}]{level:7s}[/] "
            f"[#e2e8f0]{msg}[/]"
        )

    @on(Button.Pressed, "#log-pause")
    def on_pause(self, event: Button.Pressed) -> None:
        """Toggle pause/resume polling."""
        btn = self.query_one("#log-pause", Button)
        self._polling = not self._polling
        if self._polling:
            btn.label = "⏸ Pause"
            self._start_polling()
        else:
            btn.label = "▶ Resume"

    @on(Button.Pressed, "#log-clear")
    def on_clear(self) -> None:
        """Clear the log display."""
        output = self.query_one("#logs-output", RichLog)
        output.clear()
        self._log_entries.clear()
        output.write("[dim #64748b]Logs cleared[/]")

    @on(Button.Pressed, "#log-refresh")
    async def on_refresh(self) -> None:
        """Force refresh logs."""
        self._log_entries.clear()
        output = self.query_one("#logs-output", RichLog)
        output.clear()
        await self._poll_logs()

    @on(Input.Submitted, "#log-filter")
    async def on_filter(self, event: Input.Submitted) -> None:
        """Apply filter to log display."""
        self._filter = event.value.strip()
        # Redisplay entries with filter
        output = self.query_one("#logs-output", RichLog)
        output.clear()
        self._log_entries.clear()
        # Re-fetch and filter
        await self._poll_logs()

    async def refresh_data(self) -> None:
        """Refresh logs on demand."""
        await self._poll_logs()
