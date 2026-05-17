"""
NEXUS TUI — Terminal Panel

Provides a live terminal/shell experience using asyncio subprocess.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

from textual.containers import Container, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, RichLog, Static

# ═══════════════════════════════════════════════════════════════════════
# Terminal Panel Styles
# ═══════════════════════════════════════════════════════════════════════

TERMINAL_CSS = """
TerminalPanel {
    height: 100%;
}

#terminal-container {
    height: 100%;
}

#terminal-output {
    height: 1fr;
    background: #0a0a0f;
    border: none;
    padding: 1;
}

#terminal-input-container {
    height: 5;
    background: #0f0f1a;
    border-top: solid #1e1e32;
    padding: 1 1;
}

#terminal-input {
    background: #14141f;
    color: #e2e8f0;
    border: solid #1e1e32;
    height: 3;
}

#terminal-input:focus {
    border: solid #00d4aa;
}

.term-prompt {
    color: #22c55e;
    text-style: bold;
}

.term-output {
    color: #e2e8f0;
}

.term-error {
    color: #ef4444;
}

.term-system {
    color: #64748b;
    text-style: italic;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Terminal Panel
# ═══════════════════════════════════════════════════════════════════════

class TerminalPanel(Container):
    """Live terminal panel that runs commands via asyncio subprocess."""

    CSS = TERMINAL_CSS

    def __init__(self) -> None:
        super().__init__()
        self._current_dir = os.getcwd()
        self._process: asyncio.subprocess.Process | None = None
        self._prompt = f"nexus@agent:{self._short_path(self._current_dir)}$ "

    def compose(self) -> ComposeResult:
        with Vertical(id="terminal-container"):
            yield RichLog(id="terminal-output", highlight=True, markup=True)
            with Container(id="terminal-input-container"):
                yield Input(
                    placeholder="Enter a shell command...",
                    id="terminal-input",
                )

    def on_mount(self) -> None:
        """Display welcome message."""
        output = self.query_one("#terminal-output", RichLog)
        output.write("[bold #00d4aa]╔══════════════════════════════════════╗[/]")
        output.write("[bold #00d4aa]║     NEXUS Agent — Terminal Shell     ║[/]")
        output.write("[bold #00d4aa]╚══════════════════════════════════════╝[/]")
        output.write(f"[#64748b]Type any command and press Enter to execute.[/]")
        output.write(f"[#64748b]Working directory: {self._current_dir}[/]")
        output.write(f"[#64748b]Use 'cd <dir>' to change directory.[/]")
        output.write("")
        self._write_prompt()

    def _short_path(self, path: str) -> str:
        """Shorten a path for display."""
        home = os.path.expanduser("~")
        if path.startswith(home):
            return f"~{path[len(home):]}"
        return path

    def _write_prompt(self) -> None:
        """Write the shell prompt."""
        output = self.query_one("#terminal-output", RichLog)
        self._prompt = f"[bold #22c55e]nexus[/][#64748b]@[/][bold #00d4aa]agent[/] [dim]{self._short_path(self._current_dir)}[/][#64748b]$ [/]"
        output.write(self._prompt, end="")

    @on(Input.Submitted, "#terminal-input")
    async def on_terminal_input(self, event: Input.Submitted) -> None:
        """Handle terminal command input."""
        inp = self.query_one("#terminal-input", Input)
        cmd = inp.value.strip()
        inp.clear()

        if not cmd:
            self._write_prompt()
            return

        output = self.query_one("#terminal-output", RichLog)

        # Handle cd specially
        if cmd.startswith("cd "):
            new_dir = cmd[3:].strip()
            if not new_dir:
                new_dir = os.path.expanduser("~")
            try:
                os.chdir(new_dir)
                self._current_dir = os.getcwd()
            except Exception as exc:
                output.write(f"[bold #ef4444]cd: {exc}[/]")
            self._write_prompt()
            return

        if cmd in ("exit", "quit"):
            output.write("[dim #64748b]Use Ctrl+C to quit the application.[/]")
            self._write_prompt()
            return

        # Execute the command
        try:
            # Show command in output
            output.write(f"[dim #64748b]$ {cmd}[/]")

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._current_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=30.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                output.write("[bold #ef4444]Command timed out (30s)[/]")
                self._write_prompt()
                return

            if stdout:
                for line in stdout.decode(errors="replace").splitlines():
                    output.write(f"[#e2e8f0]{line}[/]")

            if stderr:
                for line in stderr.decode(errors="replace").splitlines():
                    output.write(f"[bold #ef4444]{line}[/]")

            if proc.returncode != 0:
                output.write(
                    f"[dim #ef4444]Process exited with code {proc.returncode}[/]"
                )

        except FileNotFoundError:
            output.write(f"[bold #ef4444]Command not found: {cmd.split()[0]}[/]")
        except Exception as exc:
            output.write(f"[bold #ef4444]Error: {exc}[/]")

        self._write_prompt()
        output.scroll_end(animate=False)

    async def refresh_data(self) -> None:
        """Refresh the terminal panel."""
        pass
