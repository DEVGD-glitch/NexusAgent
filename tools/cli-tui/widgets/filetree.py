"""
NEXUS TUI — File Tree Panel

Provides a filesystem tree navigator with file preview.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

# ═══════════════════════════════════════════════════════════════════════
# File Tree Panel Styles
# ═══════════════════════════════════════════════════════════════════════

FILETREE_CSS = """
FileTreePanel {
    height: 100%;
}

#filetree-container {
    height: 100%;
}

#filetree-explorer {
    height: 1fr;
    background: #0a0a0f;
    border: solid #1e1e32;
}

#filetree-preview {
    height: 2fr;
    background: #0f0f1a;
    border: solid #1e1e32;
    margin: 0;
    padding: 1;
}

.filetree-current-dir {
    height: 1;
    background: #14141f;
    color: #00d4aa;
    text-style: bold;
    padding: 0 1;
}

Tree {
    background: #0a0a0f;
}

Tree:focus {
    border: solid #00d4aa;
}

Tree > .tree--label {
    color: #e2e8f0;
}

Tree > .tree--label.highlight {
    color: #00d4aa;
}

Tree > .tree--cursor {
    background: #1a1a2e;
}

Tree > .tree--guides {
    color: #1e1e32;
}

/* Directory nodes */
TreeNode.-dir > .tree--label {
    color: #22c55e;
}

/* File nodes */
TreeNode.-file > .tree--label {
    color: #e2e8f0;
}

/* Preview */
#preview-title {
    color: #00d4aa;
    text-style: bold;
    height: 1;
    padding: 0 1;
    background: #14141f;
}

#preview-content {
    color: #e2e8f0;
    padding: 0 1;
    background: #0a0a0f;
    height: 1fr;
    overflow-y: auto;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# File Tree Panel
# ═══════════════════════════════════════════════════════════════════════

class FileTreePanel(Container):
    """Filesystem tree navigator with file preview."""

    CSS = FILETREE_CSS

    def __init__(self) -> None:
        super().__init__()
        self._root_path = Path.cwd()
        self._node_map: dict[str, TreeNode] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="filetree-container"):
            yield Static("", id="filetree-current-dir", classes="filetree-current-dir")
            yield Tree("Filesystem", id="filetree-explorer")
            with Vertical(id="filetree-preview"):
                yield Static("Select a file to preview", id="preview-title")
                yield Static("", id="preview-content")

    def on_mount(self) -> None:
        """Initialize the file tree."""
        self._refresh_dir_label()
        tree = self.query_one("#filetree-explorer", Tree)
        tree.root.expand()
        self._populate_tree(tree.root, self._root_path)

    def _refresh_dir_label(self) -> None:
        """Update the current directory label."""
        label = self.query_one("#filetree-current-dir", Static)
        label.update(f"📁 {self._root_path.resolve()}")

    def _populate_tree(
        self, node: TreeNode, path: Path, depth: int = 0
    ) -> None:
        """Populate a tree node with directory contents."""
        if depth > 4:
            return  # Don't recurse too deep

        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            node.label = f"[dim]⛔ {path.name} (access denied)[/]"
            return
        except OSError:
            return

        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue  # Skip hidden files/dirs

            try:
                if entry.is_dir():
                    child = node.add(f"[bold #22c55e]📁 {name}[/]", expand=False)
                    self._populate_tree(child, entry, depth + 1)
                else:
                    size = entry.stat().st_size
                    size_str = self._format_size(size)
                    child = node.add(f"📄 {name} [dim]{size_str}[/]")
            except OSError:
                continue

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f}GB"

    @on(Tree.NodeSelected, "#filetree-explorer")
    async def on_file_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file selection."""
        label = event.node.label.plain

        # Extract the file name from the tree label
        # Format: "📄 filename.ext [size]"
        if label.startswith("📁"):
            # Toggle directory expansion
            event.node.toggle()
            return

        # It's a file — extract path
        file_name = label.split("[")[0].replace("📄 ", "").strip()

        # Find the actual file path by traversing the tree
        path_parts: list[str] = [file_name]
        parent = event.node.parent
        while parent and parent.label:
            parent_label = parent.label.plain
            if parent_label.startswith("📁 "):
                dir_name = parent_label.replace("📁 ", "").strip()
                path_parts.insert(0, dir_name)
            elif parent_label == "Filesystem":
                break
            parent = parent.parent

        file_path = self._root_path.joinpath(*path_parts[1:]).resolve()

        if file_path.exists() and file_path.is_file():
            await self._preview_file(file_path)

    async def _preview_file(self, path: Path) -> None:
        """Show file preview."""
        title = self.query_one("#preview-title", Static)
        content = self.query_one("#preview-content", Static)

        title.update(f"📄 {path.name} [dim]{self._format_size(path.stat().st_size)}[/]")

        try:
            if path.suffix in (".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go",
                              ".html", ".css", ".json", ".yaml", ".yml", ".toml",
                              ".md", ".txt", ".cfg", ".ini", ".conf", ".sh", ".bat",
                              ".sql", ".env.example", ".gitignore"):
                text = path.read_text(encoding="utf-8", errors="replace")
                # Truncate if too long
                if len(text) > 5000:
                    text = text[:5000] + "\n\n[dim #64748b]... (file truncated, 5000 chars shown)[/]"
                content.update(f"[#e2e8f0]{text}[/]")
            else:
                # Binary or unknown file
                content.update(
                    f"[dim #64748b]Binary or unsupported file type: {path.suffix}[/]"
                )
        except Exception as exc:
            content.update(f"[bold #ef4444]Error reading file: {exc}[/]")

    async def refresh_data(self) -> None:
        """Refresh the file tree."""
        # Rebuild the tree
        tree = self.query_one("#filetree-explorer", Tree)
        tree.clear()
        self._root_path = Path.cwd()
        self._refresh_dir_label()
        self._populate_tree(tree.root, self._root_path)
        tree.root.expand()

    def cd(self, path_str: str) -> None:
        """Change the root directory of the file tree."""
        new_path = Path(path_str).expanduser().resolve()
        if new_path.exists() and new_path.is_dir():
            self._root_path = new_path
            self._refresh_dir_label()
            tree = self.query_one("#filetree-explorer", Tree)
            tree.clear()
            self._populate_tree(tree.root, self._root_path)
            tree.root.expand()
