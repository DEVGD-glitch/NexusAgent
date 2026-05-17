"""
NEXUS TUI — Main Application

The central Textual App that orchestrates all panels, the command bar,
status bar, and tab navigation for the NEXUS Terminal UI.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import AsyncIterator, Optional

import httpx
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    TabbedContent,
    TabPane,
    Static,
)

# ── Widgets ──────────────────────────────────────────────────────────
from widgets.chat import ChatPanel
from widgets.terminal import TerminalPanel
from widgets.filetree import FileTreePanel
from widgets.logs import LogsPanel
from widgets.metrics import MetricsPanel
from widgets.approvals import ApprovalsPanel
from widgets.agent_monitor import AgentMonitorPanel

# ── Command Bar ──────────────────────────────────────────────────────
from commands.registry import CommandRegistry
from commands.builtins import register_builtins

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

NEXUS_API_BASE = "http://127.0.0.1:8081"
CSS = """
Screen {
    background: #0a0a0f;
}

NexusTUI {
    background: #0a0a0f;
}

/* ── Header ─────────────────────────────────────────────────────── */
#header {
    background: #0f0f1a;
    color: #00d4aa;
    text-style: bold;
    height: 1;
    padding: 0 1;
}

/* ── Tabbed Content ─────────────────────────────────────────────── */
TabbedContent {
    background: #0a0a0f;
    border: none;
}

TabbedContent > HeaderBar {
    background: #14141f;
    color: #64748b;
    text-style: bold;
}

TabbedContent > HeaderBar:focus-within {
    color: #00d4aa;
}

TabbedContent > HeaderBar > Tab {
    background: #14141f;
    color: #64748b;
    padding: 0 2;
    margin: 0 1;
}

TabbedContent > HeaderBar > Tab.-active {
    color: #00d4aa;
    text-style: bold;
    background: #1a1a2e;
}

TabbedContent > HeaderBar > Tab:hover {
    color: #e2e8f0;
    background: #1e1e32;
}

TabPane {
    background: #0a0a0f;
}

/* ── Status Bar ─────────────────────────────────────────────────── */
#status-bar {
    background: #0f0f1a;
    color: #64748b;
    height: 1;
    padding: 0 1;
    layout: horizontal;
}

#status-bar > Label {
    padding: 0 1;
}

.status-mode {
    color: #00d4aa;
    text-style: bold;
}

.status-provider {
    color: #7c3aed;
}

.status-connection {
    color: #22c55e;
}

.status-connection.disconnected {
    color: #ef4444;
}

.status-time {
    color: #64748b;
}

/* ── Command Bar ────────────────────────────────────────────────── */
#command-bar-container {
    height: 3;
    background: #0f0f1a;
    border-top: solid #1e1e32;
}

#command-bar {
    background: #14141f;
    color: #e2e8f0;
    border: none;
    margin: 0 1;
}

#command-bar:focus {
    border: none;
}

#command-prefix {
    color: #00d4aa;
    text-style: bold;
    padding: 0 0 0 1;
    background: #0f0f1a;
    height: 3;
    content-align: center middle;
}

/* ── Bottom Bar ─────────────────────────────────────────────────── */
#bottom-bar {
    height: 1;
    background: #0a0a0f;
}

/* ── Splash / Welcome ───────────────────────────────────────────── */
#splash {
    align: center middle;
}

#splash-box {
    width: 60;
    height: 12;
    border: solid #00d4aa;
    background: #14141f;
    padding: 1 2;
}

#splash-title {
    content-align: center middle;
    color: #00d4aa;
    text-style: bold;
    height: 3;
}

#splash-subtitle {
    content-align: center middle;
    color: #64748b;
    height: 1;
}

#splash-commands {
    content-align: center middle;
    color: #7c3aed;
    height: 2;
}

/* ── Error Notification ─────────────────────────────────────────── */
.error-toast {
    background: #7f1d1d;
    color: #fca5a5;
    border: solid #ef4444;
    padding: 1 2;
    margin: 0 4;
    height: 3;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Main App
# ═══════════════════════════════════════════════════════════════════════

class NexusTUI(App):
    """NEXUS Terminal User Interface — main application class."""

    TITLE = "NEXUS Agent"
    SUB_TITLE = "Universal Sovereign AI Agent — Terminal Interface"
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+p", "focus_command_bar", "Command Bar"),
        Binding("ctrl+t", "focus_tabs", "Tabs"),
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    # Reactive state
    connection_status: reactive[str] = reactive("disconnected")
    current_mode: reactive[str] = reactive("chat")
    active_provider: reactive[str] = reactive("auto")
    nexus_version: reactive[str] = reactive("—")

    def __init__(self) -> None:
        super().__init__()
        self.api_base = NEXUS_API_BASE
        self.http_client: httpx.AsyncClient | None = None
        self._cmd_registry: CommandRegistry | None = None
        self._status_task: asyncio.Task | None = None
        self._backend_available = False

    # ── Lifecycle ──────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Static(id="header")
        with TabbedContent(initial="chat"):
            with TabPane("💬 Chat", id="chat"):
                yield ChatPanel()
            with TabPane("🖥 Terminal", id="terminal"):
                yield TerminalPanel()
            with TabPane("📁 Files", id="files"):
                yield FileTreePanel()
            with TabPane("📋 Logs", id="logs"):
                yield LogsPanel()
            with TabPane("📊 Metrics", id="metrics"):
                yield MetricsPanel()
            with TabPane("✅ Approvals", id="approvals"):
                yield ApprovalsPanel()
            with TabPane("🤖 Agents", id="agents"):
                yield AgentMonitorPanel()
        with Horizontal(id="command-bar-container"):
            yield Label("⏎", id="command-prefix")
            yield Input(placeholder="/help for commands  |  Type a message or command...", id="command-bar")
        with Horizontal(id="status-bar"):
            yield Label("● NEXUS", id="status-mode", classes="status-mode")
            yield Label("", id="status-provider", classes="status-provider")
            yield Label("", id="status-connection", classes="status-connection")
            yield Label("", id="status-time", classes="status-time",)
        yield Static(id="bottom-bar")

    def on_mount(self) -> None:
        """Called when the app is mounted and ready."""
        self.http_client = httpx.AsyncClient(base_url=self.api_base, timeout=10.0)
        self._cmd_registry = CommandRegistry()
        register_builtins(self._cmd_registry, self)

        # Start background tasks
        self._status_task = asyncio.create_task(self._poll_status())
        self.set_interval(1.0, self._update_clock)

        # Check backend
        self._check_backend()

        # Show welcome
        self._update_status_bar()

    def on_unmount(self) -> None:
        """Cleanup on shutdown."""
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
        if self.http_client:
            asyncio.create_task(self.http_client.aclose())

    # ── Backend Communication ──────────────────────────────────────

    @work(thread=True)
    async def _check_backend(self) -> None:
        """Check if the NEXUS backend is reachable."""
        try:
            client = httpx.AsyncClient(base_url=self.api_base, timeout=5.0)
            resp = await client.get("/status")
            if resp.status_code == 200:
                data = resp.json()
                self.nexus_version = data.get("version", "—")
                self.connection_status = "connected"
                self._backend_available = True
                self.current_mode = data.get("environment", "development")
                self.active_provider = "auto"
                self.notify("Connected to NEXUS backend", severity="information", timeout=3)
            await client.aclose()
        except Exception:
            self.connection_status = "disconnected"
            self._backend_available = False
            self.notify(
                "NEXUS backend not reachable. Start the server with: nexus serve",
                severity="warning",
                timeout=5,
            )

    async def _poll_status(self) -> None:
        """Periodically poll backend status."""
        while True:
            try:
                await asyncio.sleep(5)
                if not self.http_client:
                    continue
                resp = await self.http_client.get("/status")
                if resp.status_code == 200:
                    data = resp.json()
                    self.connection_status = "connected"
                    self._backend_available = True
                else:
                    self.connection_status = "disconnected"
                    self._backend_available = False
            except Exception:
                self.connection_status = "disconnected"
                self._backend_available = False

    def _update_clock(self) -> None:
        """Update the clock in the status bar."""
        try:
            now = datetime.now().strftime("%H:%M:%S")
            status_time = self.query_one("#status-time", Label)
            status_time.update(f"🕐 {now}")
        except NoMatches:
            pass

    def _update_status_bar(self) -> None:
        """Update all status bar labels."""
        try:
            mode_label = self.query_one("#status-mode", Label)
            mode_label.update(f"● NEXUS {self.nexus_version}")

            provider_label = self.query_one("#status-provider", Label)
            provider_label.update(f"⚡ {self.active_provider}")

            conn_label = self.query_one("#status-connection", Label)
            if self.connection_status == "connected":
                conn_label.update("🟢 Connected")
                conn_label.classes = "status-connection"
            else:
                conn_label.update("🔴 Disconnected")
                conn_label.classes = "status-connection disconnected"
        except NoMatches:
            pass

    def watch_connection_status(self, value: str) -> None:
        """React to connection status changes."""
        self._update_status_bar()

    def watch_active_provider(self, value: str) -> None:
        """React to provider changes."""
        self._update_status_bar()

    def watch_nexus_version(self, value: str) -> None:
        """React to version changes."""
        self._update_status_bar()

    # ── Command Bar Handling ───────────────────────────────────────

    def focus_command_bar(self) -> None:
        """Focus the command bar input."""
        try:
            cmd_bar = self.query_one("#command-bar", Input)
            cmd_bar.focus()
        except NoMatches:
            pass

    @on(Input.Submitted, "#command-bar")
    async def on_command_submitted(self, event: Input.Submitted) -> None:
        """Handle command submitted from the command bar."""
        cmd_bar = self.query_one("#command-bar", Input)
        raw = cmd_bar.value.strip()
        cmd_bar.clear()

        if not raw:
            return

        # Determine if it's a command (starts with /) or a chat message
        if raw.startswith("/"):
            await self._execute_command(raw)
        else:
            # Send as chat message
            await self._send_chat_message(raw)

    async def _execute_command(self, raw: str) -> None:
        """Parse and execute a slash command."""
        parts = raw[1:].split(maxsplit=1)
        cmd_name = parts[0].lower() if parts else ""
        cmd_args = parts[1] if len(parts) > 1 else ""

        if self._cmd_registry:
            result = await self._cmd_registry.execute(cmd_name, cmd_args)
            if result:
                self.notify(result, timeout=3)

    async def _send_chat_message(self, message: str) -> None:
        """Send a chat message to the NEXUS backend."""
        try:
            tab_content = self.query_one("#chat", TabPane)
            chat_panel = tab_content.query_one(ChatPanel)
            await chat_panel.send_message(message)
            # Switch to chat tab
            tabs = self.query_one(TabbedContent)
            tabs.active = "chat"
        except NoMatches:
            self.notify("Chat panel not available", severity="error", timeout=3)

    # ── Tab Navigation ─────────────────────────────────────────────

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab activation."""
        tab_id = event.tab.id or ""
        name = tab_id.replace("tab-", "")
        self.current_mode = name

    def focus_tabs(self) -> None:
        """Focus the tab bar."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.focus()
        except NoMatches:
            pass

    # ── HTTP Helpers ───────────────────────────────────────────────

    async def api_get(self, path: str) -> dict | None:
        """Perform a GET request to the NEXUS backend."""
        if not self.http_client:
            return None
        try:
            resp = await self.http_client.get(path)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            return None
        return None

    async def api_post(self, path: str, data: dict | None = None) -> dict | None:
        """Perform a POST request to the NEXUS backend."""
        if not self.http_client:
            return None
        try:
            resp = await self.http_client.post(path, json=data or {})
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            return None
        return None

    async def api_stream(self, path: str, data: dict) -> AsyncIterator[dict]:
        """Stream SSE events from the NEXUS backend."""
        if not self.http_client:
            return
        try:
            async with self.http_client.stream("POST", path, json=data) as resp:
                if resp.status_code != 200:
                    return
                buffer = ""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk.decode()
                    while "\n\n" in buffer:
                        event_block, buffer = buffer.split("\n\n", 1)
                        for line in event_block.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    yield json.loads(line[6:])
                                except json.JSONDecodeError:
                                    pass
        except Exception:
            pass

    # ── Actions ────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        """Refresh all panels."""
        self.notify("Refreshing all panels...", timeout=2)
        # Trigger refresh on visible panels
        try:
            for pane in self.query(TabPane):
                for widget in pane.children:
                    if hasattr(widget, "refresh_data"):
                        asyncio.create_task(widget.refresh_data())
        except NoMatches:
            pass

