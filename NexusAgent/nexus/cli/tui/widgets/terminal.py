"""Terminal Panel — Live command execution output."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, Input, RichLog
from textual.binding import Binding
from rich.syntax import Syntax


class TerminalPanel(Vertical):
    """Terminal-like panel for command execution and output."""

    BINDINGS = [
        Binding("enter", "submit", "Execute", show=False),
    ]

    def compose(self):
        yield Static("[bold]Terminal[/] — Execute commands", id="terminal-header")
        yield RichLog(
            id="terminal-log",
            wrap=True,
            highlight=True,
            markup=True,
            auto_scroll=True,
        )
        yield Input(
            placeholder="$ Enter command...",
            id="terminal-input",
        )

    def on_mount(self) -> None:
        log = self.query_one("#terminal-log", RichLog)
        log.write("[dim]Ready. Type a command and press Enter.[/]")

    def add_output(self, text: str, is_error: bool = False) -> None:
        log = self.query_one("#terminal-log", RichLog)
        if is_error:
            log.write(f"[red]{text}[/]")
        else:
            log.write(text)

    def add_command(self, cmd: str) -> None:
        log = self.query_one("#terminal-log", RichLog)
        log.write(f"[bold cyan]$[/] {cmd}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if not cmd:
            return

        input_widget = self.query_one("#terminal-input", Input)
        input_widget.value = ""

        self.add_command(cmd)
        await self._execute(cmd)

    async def _execute(self, cmd: str) -> None:
        import asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if stdout:
                self.add_output(stdout.decode(errors="replace").rstrip())
            if stderr:
                self.add_output(stderr.decode(errors="replace").rstrip(), is_error=True)
            if proc.returncode != 0:
                self.add_output(f"[dim]Exit code: {proc.returncode}[/]", is_error=True)
        except Exception as exc:
            self.add_output(f"Failed to execute: {exc}", is_error=True)
