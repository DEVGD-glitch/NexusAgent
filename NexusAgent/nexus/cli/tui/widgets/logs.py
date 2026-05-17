"""Logs Panel — Real-time log viewer."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime

from textual.containers import Vertical
from textual.widgets import Static, RichLog, Input
from textual.binding import Binding


class LogHandler(logging.Handler):
    """Custom logging handler that feeds into the LogsPanel."""

    def __init__(self, panel: "LogsPanel") -> None:
        super().__init__()
        self._panel = panel
        self._buffer: deque[str] = deque(maxlen=500)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._buffer.append(msg)
            if self._panel.is_attached:
                self._panel._append_log(msg, record.levelno)
        except Exception:
            pass


class LogsPanel(Vertical):
    """Real-time log viewer with filtering."""

    LEVEL_COLORS = {
        logging.DEBUG: "dim",
        logging.INFO: "white",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "bold red",
    }

    BINDINGS = [
        Binding("d", "filter_debug", "Debug"),
        Binding("i", "filter_info", "Info"),
        Binding("w", "filter_warn", "Warn"),
        Binding("e", "filter_error", "Error"),
        Binding("a", "filter_all", "All"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._min_level: int = logging.DEBUG
        self._handler: LogHandler | None = None

    def compose(self):
        yield Static(
            "[bold]Logs[/] — [dim]d:Debug i:Info w:Warn e:Error a:All[/]",
            id="logs-header",
        )
        yield RichLog(
            id="logs-log",
            wrap=True,
            highlight=True,
            markup=True,
            auto_scroll=True,
        )

    def on_mount(self) -> None:
        self._handler = LogHandler(self)
        self._handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root = logging.getLogger()
        root.addHandler(self._handler)

    def on_unmount(self) -> None:
        if self._handler:
            logging.getLogger().removeHandler(self._handler)

    def _append_log(self, msg: str, level: int) -> None:
        if level < self._min_level:
            return
        color = self.LEVEL_COLORS.get(level, "white")
        log = self.query_one("#logs-log", RichLog)
        log.write(f"[{color}]{msg}[/]")

    def action_filter_debug(self) -> None:
        self._min_level = logging.DEBUG
        self.app.notify("Filter: DEBUG+", severity="information")

    def action_filter_info(self) -> None:
        self._min_level = logging.INFO
        self.app.notify("Filter: INFO+", severity="information")

    def action_filter_warn(self) -> None:
        self._min_level = logging.WARNING
        self.app.notify("Filter: WARNING+", severity="information")

    def action_filter_error(self) -> None:
        self._min_level = logging.ERROR
        self.app.notify("Filter: ERROR+", severity="information")

    def action_filter_all(self) -> None:
        self._min_level = logging.DEBUG
        self.app.notify("Filter: ALL", severity="information")
