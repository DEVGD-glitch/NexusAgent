"""
NEXUS Audit Logger — Comprehensive audit trail for all agent actions.

Records every action, decision, tool call, and data access for
compliance, debugging, and security review. Audit logs are
immutable and append-only.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class AuditLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditCategory(str, Enum):
    AUTH = "auth"
    TOOL_CALL = "tool_call"
    MEMORY_ACCESS = "memory_access"
    CODE_EXECUTION = "code_execution"
    LLM_CALL = "llm_call"
    CONFIG_CHANGE = "config_change"
    AGENT_ACTION = "agent_action"
    DATA_ACCESS = "data_access"
    SECURITY = "security"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    category: AuditCategory = AuditCategory.AGENT_ACTION
    level: AuditLevel = AuditLevel.INFO
    action: str = ""
    actor: str = "nexus"
    target: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""  # success, failure, denied
    session_id: str = ""
    request_id: str = ""
    ip_address: str = ""

    def to_json(self) -> str:
        """Serialize to a single-line JSON for log file storage."""
        return json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "level": self.level.value,
            "action": self.action,
            "actor": self.actor,
            "target": self.target,
            "details": self.details,
            "outcome": self.outcome,
            "session_id": self.session_id,
            "request_id": self.request_id,
        }, ensure_ascii=False, default=str)


class AuditLogger:
    """
    Immutable audit logger for NEXUS.

    Writes audit entries to:
      1. Python logging (for console/log aggregation)
      2. JSONL file (for persistent storage and analysis)
      3. Optional OpenTelemetry export

    Audit logs are append-only — entries cannot be deleted or modified.

    Usage:
        audit = AuditLogger()
        audit.log(
            category=AuditCategory.TOOL_CALL,
            action="execute_code",
            target="python_subprocess",
            details={"code_length": 150},
            outcome="success",
        )
    """

    def __init__(self, log_dir: Optional[str] = None):
        settings = get_settings()
        self.log_dir = Path(log_dir or settings.audit_log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[Path] = None
        self._file_handle = None
        self._entries_count = 0
        atexit.register(self.close)

    def _get_log_file(self) -> Path:
        """Get the current log file path (one per day)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"nexus_audit_{today}.jsonl"

    def _ensure_file(self):
        """Ensure the log file is open for appending."""
        log_file = self._get_log_file()
        if self._current_file != log_file:
            if self._file_handle:
                old_handle = self._file_handle
                self._file_handle = None
                try:
                    old_handle.close()
                except Exception as e:
                    logger.error("Failed to close previous audit log handle: %s", e)
            try:
                self._file_handle = open(log_file, "a", encoding="utf-8")
                self._current_file = log_file
            except Exception as e:
                logger.error("Failed to open audit log file %s: %s", log_file, e)
                self._current_file = None

    def log(
        self,
        category: AuditCategory = AuditCategory.AGENT_ACTION,
        level: AuditLevel = AuditLevel.INFO,
        action: str = "",
        actor: str = "nexus",
        target: str = "",
        details: Optional[dict[str, Any]] = None,
        outcome: str = "",
        session_id: str = "",
        request_id: str = "",
    ) -> str:
        """
        Record an audit entry.

        Args:
            category: Type of auditable event.
            level: Severity level.
            action: What action was taken.
            actor: Who performed the action.
            target: What was acted upon.
            details: Additional context.
            outcome: Result (success, failure, denied).
            session_id: Session identifier.
            request_id: Request identifier.

        Returns:
            The event_id of the logged entry.
        """
        entry = AuditEntry(
            category=category,
            level=level,
            action=action,
            actor=actor,
            target=target,
            details=details or {},
            outcome=outcome,
            session_id=session_id,
            request_id=request_id,
        )

        # Write to Python logger
        log_msg = f"[AUDIT] {entry.category.value}:{entry.action} outcome={entry.outcome} target={entry.target}"
        if entry.level == AuditLevel.CRITICAL:
            logger.critical(log_msg)
        elif entry.level == AuditLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Write to JSONL file
        try:
            self._ensure_file()
            if self._file_handle:
                self._file_handle.write(entry.to_json() + "\n")
                self._file_handle.flush()
        except Exception as e:
            logger.error("Failed to write audit entry to file: %s", e)

        self._entries_count += 1
        return entry.event_id

    def log_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
        outcome: str,
        execution_time_ms: float = 0.0,
        session_id: str = "",
    ) -> str:
        """Convenience method for logging tool calls."""
        return self.log(
            category=AuditCategory.TOOL_CALL,
            action="call",
            target=tool_name,
            details={"params": params, "execution_time_ms": execution_time_ms},
            outcome=outcome,
            session_id=session_id,
        )

    def log_llm_call(
        self,
        provider: str,
        model: str,
        tokens_used: int,
        cost_usd: float,
        outcome: str = "success",
        session_id: str = "",
    ) -> str:
        """Convenience method for logging LLM API calls."""
        return self.log(
            category=AuditCategory.LLM_CALL,
            action="complete",
            target=f"{provider}/{model}",
            details={"tokens": tokens_used, "cost_usd": cost_usd},
            outcome=outcome,
            session_id=session_id,
        )

    def log_memory_access(
        self,
        operation: str,
        namespace: str,
        doc_id: str = "",
        outcome: str = "success",
        session_id: str = "",
    ) -> str:
        """Convenience method for logging memory access."""
        return self.log(
            category=AuditCategory.MEMORY_ACCESS,
            action=operation,
            target=f"{namespace}/{doc_id}" if doc_id else namespace,
            outcome=outcome,
            session_id=session_id,
        )

    def log_security_event(
        self,
        event_type: str,
        reason: str,
        severity: AuditLevel = AuditLevel.WARNING,
        details: Optional[dict[str, Any]] = None,
    ) -> str:
        """Convenience method for logging security events."""
        return self.log(
            category=AuditCategory.SECURITY,
            level=severity,
            action=event_type,
            target="security_boundary",
            details={"reason": reason, **(details or {})},
            outcome="denied",
        )

    def query(
        self,
        category: Optional[AuditCategory] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit log entries with filters.

        Args:
            category: Filter by category.
            action: Filter by action.
            outcome: Filter by outcome.
            since: ISO timestamp to start from.
            limit: Maximum entries to return.

        Returns:
            List of matching audit entries.
        """
        entries = []
        log_files = sorted(self.log_dir.glob("nexus_audit_*.jsonl"), reverse=True)

        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Apply filters
                        if category and entry.get("category") != category.value:
                            continue
                        if action and entry.get("action") != action:
                            continue
                        if outcome and entry.get("outcome") != outcome:
                            continue
                        if since and entry.get("timestamp", "") < since:
                            continue

                        entries.append(entry)
                        if len(entries) >= limit:
                            return entries
            except FileNotFoundError:
                continue

        return entries

    def get_stats(self) -> dict[str, Any]:
        """Get audit log statistics."""
        log_files = list(self.log_dir.glob("nexus_audit_*.jsonl"))
        total_size = sum(f.stat().st_size for f in log_files if f.exists())
        return {
            "entries_logged": self._entries_count,
            "log_files": len(log_files),
            "total_size_bytes": total_size,
            "log_dir": str(self.log_dir),
        }

    def close(self):
        """Close the log file handle."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                logger.error("Failed to close audit log file: %s", e)
            finally:
                self._file_handle = None
                self._current_file = None
