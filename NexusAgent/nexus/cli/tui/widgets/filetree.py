"""File Tree Panel — Filesystem browser."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, DirectoryTree
from textual.binding import Binding


class FileTreePanel(Vertical):
    """Filesystem browser panel."""

    BINDINGS = [
        Binding("enter", "select", "Select", show=False),
        Binding("backspace", "go_up", "Up", show=False),
    ]

    def __init__(self, root_path: str = ".", **kwargs) -> None:
        super().__init__(**kwargs)
        self._root = Path(root_path).resolve()

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]Files[/] — {self._root}",
            id="filetree-header",
        )
        yield DirectoryTree(
            str(self._root),
            id="filetree-tree",
        )

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(str(event.path))
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                self.app.notify(f"Opened: {path.name}", severity="information")
            except Exception as exc:
                self.app.notify(f"Cannot read: {exc}", severity="error")

    def action_go_up(self) -> None:
        tree = self.query_one("#filetree-tree", DirectoryTree)
        tree.action_parent()
