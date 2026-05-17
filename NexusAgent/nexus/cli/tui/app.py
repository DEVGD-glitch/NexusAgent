"""NEXUS TUI — Main application with tabbed panels and command routing."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    TabbedContent,
    TabPane,
    Label,
)

from nexus.cli.tui.widgets.chat import ChatPanel
from nexus.cli.tui.widgets.terminal import TerminalPanel
from nexus.cli.tui.widgets.filetree import FileTreePanel
from nexus.cli.tui.widgets.logs import LogsPanel
from nexus.cli.tui.widgets.metrics import MetricsPanel
from nexus.cli.tui.widgets.approvals import ApprovalsPanel
from nexus.cli.tui.widgets.agents import AgentsPanel
from nexus.cli.tui.commands.registry import get_command_registry


class NexusTUI(App):
    """NEXUS Modern TUI Application."""

    TITLE = "NEXUS Agent"
    SUB_TITLE = "Universal Sovereign AI Agent"

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-content {
        height: 1fr;
    }
    TabPane {
        padding: 0;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    ChatPanel {
        height: 100%;
    }
    #chat-log {
        height: 1fr;
    }
    #chat-input {
        height: 3;
        dock: bottom;
    }
    TerminalPanel {
        height: 100%;
    }
    #terminal-log {
        height: 1fr;
    }
    #terminal-input {
        height: 3;
        dock: bottom;
    }
    FileTreePanel {
        height: 100%;
    }
    LogsPanel {
        height: 100%;
    }
    #logs-log {
        height: 1fr;
    }
    MetricsPanel {
        height: 100%;
    }
    ApprovalsPanel {
        height: 100%;
    }
    #approvals-log {
        height: 1fr;
    }
    AgentsPanel {
        height: 100%;
    }
    #agents-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "cycle_tabs", "Next Tab"),
        Binding("f1", "show_tab('chat')", "Chat"),
        Binding("f2", "show_tab('terminal')", "Terminal"),
        Binding("f3", "show_tab('files')", "Files"),
        Binding("f4", "show_tab('logs')", "Logs"),
        Binding("f5", "show_tab('metrics')", "Metrics"),
        Binding("f6", "show_tab('approvals')", "Approvals"),
        Binding("f7", "show_tab('agents')", "Agents"),
    ]

    def __init__(self, root_path: str = ".", **kwargs) -> None:
        super().__init__(**kwargs)
        self._root_path = root_path
        self._command_registry = get_command_registry()
        self._tab_order = ["chat", "terminal", "files", "logs", "metrics", "approvals", "agents"]
        self._current_tab_index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="chat", id="main-content"):
            with TabPane("Chat", id="chat"):
                yield ChatPanel()
            with TabPane("Terminal", id="terminal"):
                yield TerminalPanel()
            with TabPane("Files", id="files"):
                yield FileTreePanel(root_path=self._root_path)
            with TabPane("Logs", id="logs"):
                yield LogsPanel()
            with TabPane("Metrics", id="metrics"):
                yield MetricsPanel()
            with TabPane("Approvals", id="approvals"):
                yield ApprovalsPanel()
            with TabPane("Agents", id="agents"):
                yield AgentsPanel()
        yield Static(
            "  F1-7: Switch panels  |  Ctrl+L: Next tab  |  /help: Commands  |  Ctrl+Q: Quit",
            id="status-bar",
        )

    def on_mount(self) -> None:
        from textual.widgets import Input
        try:
            self.query_one("#chat-input", Input).focus()
        except Exception:
            pass

    # ── Command Handling ────────────────────────────────────────────

    async def on_chat_panel_command_executed(
        self, event: ChatPanel.CommandExecuted
    ) -> None:
        chat = self.query_one(ChatPanel)
        result = await self._command_registry.execute(event.command, event.args)

        if result == "__CLEAR__":
            chat.clear_log()
            return
        if result == "__QUIT__":
            self.exit()
            return

        if result:
            chat.add_system_message(result)

    async def on_chat_panel_message_sent(self, event: ChatPanel.MessageSent) -> None:
        chat = self.query_one(ChatPanel)
        await self._process_message(event.content, chat)

    async def _process_message(self, content: str, chat: ChatPanel) -> None:
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            from nexus.memory.chroma_service import NexusMemoryService
            from nexus.core.config import get_settings

            settings = get_settings()
            router = LLMRouter()
            memory = NexusMemoryService(persist_dir=settings.chroma_persist_dir)

            context_results = await memory.search(query=content, namespace="conversations", top_k=3)
            context_docs = context_results.get("documents", [[]])[0]

            messages = []
            if context_docs:
                context_text = "\n".join(context_docs[:3])
                messages.append({"role": "system", "content": f"Relevant context:\n{context_text}"})
            messages.append({"role": "user", "content": content})

            response = await router.complete(
                messages=messages,
                task_complexity=TaskComplexity.SIMPLE,
            )

            chat.add_assistant_message(
                response.content,
                provider=response.provider.value,
                model=response.model,
            )

            await memory.store(
                text=f"User: {content}\nAssistant: {response.content}",
                namespace="conversations",
            )

        except Exception as exc:
            chat.add_error(str(exc))

    # ── Tab Navigation ──────────────────────────────────────────────

    def action_cycle_tabs(self) -> None:
        self._current_tab_index = (self._current_tab_index + 1) % len(self._tab_order)
        tab_id = self._tab_order[self._current_tab_index]
        tabbed = self.query_one("#main-content", TabbedContent)
        tabbed.active = tab_id

    def action_show_tab(self, tab_id: str) -> None:
        tabbed = self.query_one("#main-content", TabbedContent)
        tabbed.active = tab_id
        self._current_tab_index = self._tab_order.index(tab_id)

    # ── Approval Handling ───────────────────────────────────────────

    def on_approvals_panel_approved(self, event: ApprovalsPanel.Approved) -> None:
        self.notify(f"Approved: {event.request_id}", severity="information")

    def on_approvals_panel_denied(self, event: ApprovalsPanel.Denied) -> None:
        self.notify(f"Denied: {event.request_id}", severity="warning")

    # ── Agent Action Handling ───────────────────────────────────────

    def on_agents_panel_agent_action(self, event: AgentsPanel.AgentAction) -> None:
        if event.action == "kill":
            self.notify(f"Agent {event.agent_id} killed", severity="warning")
        elif event.action == "logs":
            self.notify(f"Showing logs for {event.agent_id}")


def run_tui(root_path: str = ".") -> None:
    """Entry point for the NEXUS TUI."""
    app = NexusTUI(root_path=root_path)
    app.run()
