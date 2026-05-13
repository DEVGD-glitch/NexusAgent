"""
NEXUS Telemetry — Opt-in anonymous crash reporting.

Only collects crash reports. No usage tracking.
User must explicitly opt-in via a toast confirmation.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TelemetryManager:
    """
    Opt-in anonymous crash reporting.

    Rules:
      - Disabled by default
      - User must explicitly opt-in
      - Only crash reports are collected
      - No usage tracking, no PII
      - Reports are stored locally and can be reviewed
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or os.path.join(
            os.path.expanduser("~"), ".nexus", "telemetry"
        ))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = False
        self._consent_file = self.data_dir / "consent.json"

    def load_consent(self) -> bool:
        """Load the user's telemetry consent preference."""
        if self._consent_file.exists():
            try:
                data = json.loads(self._consent_file.read_text(encoding="utf-8"))
                self.enabled = data.get("enabled", False)
            except Exception:
                self.enabled = False
        return self.enabled

    def set_consent(self, enabled: bool) -> None:
        """Save the user's telemetry consent preference."""
        self.enabled = enabled
        self._consent_file.write_text(
            json.dumps({"enabled": enabled, "timestamp": time.time()}),
            encoding="utf-8",
        )

    def report_crash(self, error_type: str, error_message: str, traceback: str = "") -> bool:
        """
        Record a crash report locally.

        Args:
            error_type: Exception class name
            error_message: Human-readable error message
            traceback: Stack trace (sanitized)

        Returns:
            True if recorded successfully.
        """
        if not self.enabled:
            return False

        try:
            report = {
                "timestamp": time.time(),
                "error_type": error_type,
                "error_message": self._sanitize(error_message),
                "traceback": self._sanitize(traceback[:2000]),
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "nexus_version": "1.0.0",
            }

            report_file = self.data_dir / f"crash_{int(time.time())}.json"
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

            logger.info("Crash report recorded: %s", error_type)
            return True
        except Exception as exc:
            logger.error("Failed to record crash report: %s", exc)
            return False

    def _sanitize(self, text: str) -> str:
        """Remove potential PII from text."""
        import re
        # Remove file paths
        text = re.sub(r'/[^\s]+/', '[PATH]/', text)
        # Remove email addresses
        text = re.sub(r'[\w.]+@[\w.]+', '[EMAIL]', text)
        # Remove API keys patterns
        text = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[API_KEY]', text)
        text = re.sub(r'key-[a-zA-Z0-9]{20,}', '[API_KEY]', text)
        return text

    def get_pending_reports(self) -> list[dict]:
        """Get all pending crash reports."""
        reports = []
        for f in self.data_dir.glob("crash_*.json"):
            try:
                reports.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return reports

    def clear_reports(self) -> None:
        """Delete all stored crash reports."""
        for f in self.data_dir.glob("crash_*.json"):
            f.unlink()
