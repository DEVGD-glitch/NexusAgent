"""Chat Panel — Main chat interface for the NEXUS TUI."""

from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Input, RichLog
from textual.binding import Binding
from textual.message import Message
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


class ChatPanel(Vertical):
    """Chat interface with message history and input."""

    BINDINGS = [
        Binding("enter", "submit", "Send", show=False),
        Binding("escape", "focus_self", "Escape", show=False),
    ]

    class MessageSent(Message):
        """Posted when user sends a message."""
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    class CommandExecuted(Message):
        """Posted when a slash command is executed."""
        def __init__(self, command: str, args: str, result: str | None) -> None:
            self.command = command
            self.args = args
            self.result = result
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history: list[dict[str, str]] = []
        self._history_index: int = -1

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="chat-log",
            wrap=True,
            highlight=True,
            markup=True,
            auto_scroll=True,
        )
        yield Input(
            placeholder="Type a message or /command...",
            id="chat-input",
        )

    def on_mount(self) -> None:
        self._show_welcome()

    def _show_welcome(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        welcome = Panel(
            "[bold cyan]NEXUS TUI[/] — Universal Sovereign AI Agent\n\n"
            "Type your message and press [bold]Enter[/]. "
            "Use [bold]/help[/] for commands.\n"
            "Press [bold]Ctrl+L[/] to switch panels.",
            title="Welcome",
            border_style="cyan",
        )
        log.write(welcome)

    def add_user_message(self, content: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        timestamp = datetime.now().strftime("%H:%M")
        log.write(f"[dim]{timestamp}[/] [bold green]You:[/] {content}")

    def add_assistant_message(self, content: str, provider: str = "", model: str = "") -> None:
        log = self.query_one("#chat-log", RichLog)
        timestamp = datetime.now().strftime("%H:%M")
        subtitle = f" ({provider}/{model})" if provider else ""
        log.write(Panel(
            Markdown(content),
            title=f"[bold blue]NEXUS[/]{subtitle}",
            subtitle=f"[dim]{timestamp}[/]",
            border_style="blue",
        ))

    def add_system_message(self, content: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim italic]{content}[/]")

    def add_error(self, content: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold red]Error:[/] {content}")

    def clear_log(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.clear()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        if not content:
            return

        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = ""

        self._history.append(content)
        self._history_index = len(self._history)

        if content.startswith("/"):
            parts = content[1:].split(" ", 1)
            cmd_name = parts[0]
            cmd_args = parts[1] if len(parts) > 1 else ""
            self.post_message(ChatPanel.CommandExecuted(cmd_name, cmd_args, None))
        else:
            self.add_user_message(content)
            self.post_message(ChatPanel.MessageSent(content))

    def action_focus_self(self) -> None:
        self.query_one("#chat-input", Input).focus()
