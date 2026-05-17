"""Workflow Storage — Persistence for workflow definitions and execution history."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowStorage:
    """Persists workflow definitions and execution logs."""

    def __init__(self, data_dir: str | Path = "./nexus_data/workflows") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir = self.data_dir / "history"
        self.history_dir.mkdir(exist_ok=True)

    # ── Workflow CRUD ───────────────────────────────────────────

    def save_workflow(self, workflow_data: dict[str, Any]) -> bool:
        try:
            wf_id = workflow_data["id"]
            path = self.data_dir / f"{wf_id}.json"
            path.write_text(json.dumps(workflow_data, indent=2, default=str), encoding="utf-8")
            logger.info("Saved workflow: %s", wf_id)
            return True
        except Exception as exc:
            logger.error("Failed to save workflow: %s", exc)
            return False

    def load_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        path = self.data_dir / f"{workflow_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load workflow %s: %s", workflow_id, exc)
            return None

    def delete_workflow(self, workflow_id: str) -> bool:
        path = self.data_dir / f"{workflow_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_workflows(self) -> list[dict[str, Any]]:
        workflows = []
        for f in self.data_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                workflows.append(data)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", f, exc)
        return sorted(workflows, key=lambda w: w.get("name", ""))

    # ── Execution History ───────────────────────────────────────

    def save_execution(self, workflow_id: str, execution_id: str, data: dict[str, Any]) -> bool:
        try:
            wf_dir = self.history_dir / workflow_id
            wf_dir.mkdir(exist_ok=True)
            path = wf_dir / f"{execution_id}.json"
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            return True
        except Exception as exc:
            logger.error("Failed to save execution: %s", exc)
            return False

    def load_execution(self, workflow_id: str, execution_id: str) -> dict[str, Any] | None:
        path = self.history_dir / workflow_id / f"{execution_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_executions(self, workflow_id: str, limit: int = 20) -> list[dict[str, Any]]:
        wf_dir = self.history_dir / workflow_id
        if not wf_dir.exists():
            return []
        executions = []
        for f in sorted(wf_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                executions.append(data)
            except Exception:
                pass
        return executions

    def get_stats(self) -> dict[str, Any]:
        workflow_count = len(list(self.data_dir.glob("*.json")))
        execution_count = sum(1 for _ in self.history_dir.rglob("*.json"))
        return {
            "workflow_count": workflow_count,
            "execution_count": execution_count,
        }
