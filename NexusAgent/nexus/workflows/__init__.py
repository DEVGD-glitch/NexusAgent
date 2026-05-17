"""
NEXUS Workflow Engine — Triggers, conditions, actions, and execution.

Extends the basic WorkflowManager with a full event-driven workflow engine
supporting triggers, conditional logic, and multi-step execution.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    action: str  # MCP tool name
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class Workflow:
    """A reusable workflow template."""
    id: str
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    is_builtin: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [asdict(s) for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_builtin": self.is_builtin,
        }


# ── Built-in Workflows ──────────────────────────────────────────────

BUILTIN_WORKFLOWS: list[Workflow] = [
    Workflow(
        id="analyze_code",
        name="Analyse de code",
        description="Lire un fichier, l'analyser, et proposer des améliorations",
        steps=[
            WorkflowStep(name="Lire le fichier", action="read_file", params={"path": ""}, description="Chemin du fichier à analyser"),
            WorkflowStep(name="Analyser avec LLM", action="llm_complete", params={"messages_json": ""}, description="Analyser le code et proposer des améliorations"),
        ],
        is_builtin=True,
    ),
    Workflow(
        id="research_topic",
        name="Recherche approfondie",
        description="Rechercher sur le web, stocker en mémoire, et synthétiser",
        steps=[
            WorkflowStep(name="Rechercher sur le web", action="web_search", params={"query": ""}, description="Sujet de recherche"),
            WorkflowStep(name="Stocker en mémoire", action="store_memory", params={"namespace": "knowledge"}, description="Stocker les résultats"),
            WorkflowStep(name="Synthétiser", action="llm_complete", params={}, description="Créer une synthèse"),
        ],
        is_builtin=True,
    ),
    Workflow(
        id="fix_bug",
        name="Correction de bug",
        description="Lire le code, identifier le bug, proposer et appliquer le correctif",
        steps=[
            WorkflowStep(name="Lire le fichier", action="read_file", params={"path": ""}, description="Fichier avec le bug"),
            WorkflowStep(name="Analyser le bug", action="reason_react", params={"task": ""}, description="Description du bug"),
            WorkflowStep(name="Proposer le correctif", action="llm_complete", params={}, description="Générer le correctif"),
        ],
        is_builtin=True,
    ),
    Workflow(
        id="learn_topic",
        name="Apprendre un sujet",
        description="Rechercher, stocker en Knowledge Graph, et créer une synthèse",
        steps=[
            WorkflowStep(name="Rechercher", action="web_search", params={"query": ""}, description="Sujet à apprendre"),
            WorkflowStep(name="Ajouter au graphe", action="knowledge_add_entity", params={"entity_type": "concept"}, description="Entités du sujet"),
            WorkflowStep(name="Stocker en mémoire", action="store_memory", params={"namespace": "knowledge"}, description="Connaissances acquises"),
        ],
        is_builtin=True,
    ),
]


class WorkflowManager:
    """
    Manages workflow templates — built-in and user-created.

    Usage:
        manager = WorkflowManager()
        workflows = manager.list_workflows()
        manager.save_workflow(Workflow(...))
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "./nexus_data/workflows")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def list_workflows(self) -> list[Workflow]:
        """List all available workflows (built-in + user-created)."""
        workflows = list(BUILTIN_WORKFLOWS)

        # Load user-created workflows
        for f in self.data_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                steps = [WorkflowStep(**s) for s in data.get("steps", [])]
                workflows.append(Workflow(
                    id=data["id"],
                    name=data["name"],
                    description=data.get("description", ""),
                    steps=steps,
                    created_at=data.get("created_at", 0),
                    updated_at=data.get("updated_at", 0),
                    is_builtin=False,
                ))
            except Exception as exc:
                logger.warning("Failed to load workflow %s: %s", f, exc)

        return workflows

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a specific workflow by ID."""
        for wf in self.list_workflows():
            if wf.id == workflow_id:
                return wf
        return None

    def save_workflow(self, workflow: Workflow) -> bool:
        """Save a user-created workflow."""
        try:
            workflow.updated_at = time.time()
            if not workflow.created_at:
                workflow.created_at = time.time()

            filepath = self.data_dir / f"{workflow.id}.json"
            filepath.write_text(json.dumps(workflow.to_dict(), indent=2), encoding="utf-8")
            logger.info("Saved workflow: %s", workflow.id)
            return True
        except Exception as exc:
            logger.error("Failed to save workflow %s: %s", workflow.id, exc)
            return False

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a user-created workflow."""
        filepath = self.data_dir / f"{workflow_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False


# ── Re-export new engine modules ─────────────────────────────────

from nexus.workflows.triggers import (
    Trigger,
    TriggerType,
    TriggerContext,
    TriggerFactory,
    TimerTrigger,
    FileChangeTrigger,
    WebhookTrigger,
    EventTrigger,
    ManualTrigger,
)
from nexus.workflows.conditions import (
    Condition,
    SimpleCondition,
    AndCondition,
    OrCondition,
    NotCondition,
    ConditionCompiler,
)
from nexus.workflows.actions import (
    Action,
    ActionType,
    ActionResult,
    ActionFactory,
    ToolCallAction,
    LLMCallAction,
    AgentSpawnAction,
    NotifyAction,
    DelayAction,
    SetVariableAction,
    HTTPRequestAction,
    ParallelAction,
)
from nexus.workflows.engine import (
    WorkflowEngine,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    ExecutionStatus,
    get_workflow_engine,
)
from nexus.workflows.validation import validate_workflow, ValidationResult
from nexus.workflows.storage import WorkflowStorage

__all__ = [
    # Legacy
    "WorkflowStep",
    "Workflow",
    "WorkflowManager",
    # Engine
    "WorkflowEngine",
    "WorkflowDefinition",
    "WorkflowExecution",
    "WorkflowStatus",
    "ExecutionStatus",
    "get_workflow_engine",
    # Triggers
    "Trigger",
    "TriggerType",
    "TriggerContext",
    "TriggerFactory",
    # Conditions
    "Condition",
    "SimpleCondition",
    "AndCondition",
    "OrCondition",
    "NotCondition",
    "ConditionCompiler",
    # Actions
    "Action",
    "ActionType",
    "ActionResult",
    "ActionFactory",
    # Validation & Storage
    "validate_workflow",
    "ValidationResult",
    "WorkflowStorage",
]
