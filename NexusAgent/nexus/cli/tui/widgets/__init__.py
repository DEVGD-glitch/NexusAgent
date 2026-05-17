"""TUI Widgets — Composable UI panels for the NEXUS TUI."""

from nexus.cli.tui.widgets.chat import ChatPanel
from nexus.cli.tui.widgets.terminal import TerminalPanel
from nexus.cli.tui.widgets.filetree import FileTreePanel
from nexus.cli.tui.widgets.logs import LogsPanel
from nexus.cli.tui.widgets.metrics import MetricsPanel
from nexus.cli.tui.widgets.approvals import ApprovalsPanel
from nexus.cli.tui.widgets.agents import AgentsPanel

__all__ = [
    "ChatPanel",
    "TerminalPanel",
    "FileTreePanel",
    "LogsPanel",
    "MetricsPanel",
    "ApprovalsPanel",
    "AgentsPanel",
]
