"""
NEXUS TUI — Terminal User Interface for NEXUS Agent.

Launch the TUI application:
    python tools/cli-tui/main.py

Or from the project root:
    python -m tools.cli-tui.main
"""

from __future__ import annotations

import sys
import os
from pathlib import Path


def _setup_paths() -> None:
    """Ensure the NexusAgent package and tools/cli-tui are importable."""
    script_dir = Path(__file__).parent.resolve()
    nexus_root = script_dir.parent.parent / "NexusAgent"
    if str(nexus_root) not in sys.path:
        sys.path.insert(0, str(nexus_root))
    # Add script dir so local imports (app, widgets, commands) work
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))


_setup_paths()

from app import NexusTUI


def main() -> None:
    """Launch the NEXUS TUI application."""
    app = NexusTUI()
    app.run()


if __name__ == "__main__":
    main()
