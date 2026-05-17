"""Workflow Engine — Orchestrates triggers, conditions, and actions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus.workflows.triggers import Trigger, TriggerContext, TriggerFactory
from nexus.workflows.conditions import Condition, ConditionCompiler
from nexus.workflows.actions import Action, ActionResult, ActionFactory
from nexus.workflows.validation import validate_workflow
from nexus.workflows.storage import WorkflowStorage

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    step_name: str
    action_type: str
    status: ExecutionStatus
    result: ActionResult | None = None
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "action_type": self.action_type,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class WorkflowExecution:
    """A single execution of a workflow."""
    execution_id: str
    workflow_id: str
    status: ExecutionStatus
    started_at: float
    finished_at: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    step_results: list[StepResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "context": {k: v for k, v in self.context.items() if not k.startswith("_")},
            "step_results": [s.to_dict() for s in self.step_results],
            "error": self.error,
        }


@dataclass
class WorkflowDefinition:
    """A complete workflow with triggers, conditions, and steps."""
    id: str
    name: str
    description: str = ""
    triggers: list[Trigger] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    steps: list[Action] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "triggers": [t.to_dict() for t in self.triggers],
            "conditions": [c.to_dict() for c in self.conditions],
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class WorkflowEngine:
    """Main engine that manages and executes workflows."""

    def __init__(self, storage: WorkflowStorage | None = None) -> None:
        self.storage = storage or WorkflowStorage()
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._active_triggers: dict[str, list[Trigger]] = {}
        self._executions: dict[str, WorkflowExecution] = {}

    # ── Workflow Management ─────────────────────────────────────

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.id] = workflow
        logger.info("Registered workflow: %s (%s)", workflow.name, workflow.id)

    def load_from_config(self, config: dict[str, Any]) -> WorkflowDefinition:
        """Load a workflow from a config dict."""
        wf_id = config.get("id", str(uuid.uuid4()))

        triggers = [TriggerFactory.create(t) for t in config.get("triggers", [])]
        conditions = [ConditionCompiler.compile(c) for c in config.get("conditions", [])]
        steps = [ActionFactory.create(s) for s in config.get("steps", [])]

        workflow = WorkflowDefinition(
            id=wf_id,
            name=config.get("name", wf_id),
            description=config.get("description", ""),
            triggers=triggers,
            conditions=conditions,
            steps=steps,
            created_at=time.time(),
            updated_at=time.time(),
            metadata=config.get("metadata", {}),
        )
        self.register_workflow(workflow)
        return workflow

    def load_from_storage(self) -> int:
        """Load all workflows from storage."""
        configs = self.storage.list_workflows()
        for config in configs:
            try:
                self.load_from_config(config)
            except Exception as exc:
                logger.error("Failed to load workflow %s: %s", config.get("id"), exc)
        return len(configs)

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            # Stop triggers first
            self._stop_triggers(workflow_id)
            del self._workflows[workflow_id]
            self.storage.delete_workflow(workflow_id)
            return True
        return False

    # ── Activation ──────────────────────────────────────────────

    async def activate(self, workflow_id: str) -> bool:
        """Activate a workflow — start its triggers."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False

        wf.status = WorkflowStatus.ACTIVE
        self._active_triggers[workflow_id] = []

        for trigger in wf.triggers:
            trigger.on_fire(lambda ctx, _wf=wf: self._on_trigger(_wf, ctx))
            await trigger.start()
            self._active_triggers[workflow_id].append(trigger)

        logger.info("Activated workflow: %s (%d triggers)", wf.name, len(wf.triggers))
        return True

    async def deactivate(self, workflow_id: str) -> bool:
        """Deactivate a workflow — stop its triggers."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False

        wf.status = WorkflowStatus.PAUSED
        await self._stop_triggers(workflow_id)
        return True

    async def _stop_triggers(self, workflow_id: str) -> None:
        triggers = self._active_triggers.pop(workflow_id, [])
        for trigger in triggers:
            try:
                await trigger.stop()
            except Exception as exc:
                logger.error("Error stopping trigger %s: %s", trigger.trigger_id, exc)

    # ── Execution ───────────────────────────────────────────────

    async def _on_trigger(self, workflow: WorkflowDefinition, trigger_ctx: TriggerContext) -> None:
        """Called when a trigger fires."""
        context = {
            "_trigger_type": trigger_ctx.trigger_type.value,
            "_trigger_id": trigger_ctx.trigger_id,
            "_trigger_time": trigger_ctx.timestamp,
            **trigger_ctx.data,
        }
        await self.execute(workflow.id, context)

    async def execute(self, workflow_id: str, context: dict[str, Any] | None = None) -> WorkflowExecution:
        """Execute a workflow."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        execution_id = str(uuid.uuid4())[:8]
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=ExecutionStatus.RUNNING,
            started_at=time.time(),
            context=context or {},
        )
        self._executions[execution_id] = execution

        logger.info("Executing workflow %s (execution %s)", wf.name, execution_id)

        # Check conditions
        if wf.conditions:
            ctx = execution.context
            all_met = all(c.evaluate(ctx) for c in wf.conditions)
            if not all_met:
                execution.status = ExecutionStatus.SKIPPED
                execution.finished_at = time.time()
                execution.error = "Conditions not met"
                logger.info("Workflow %s skipped — conditions not met", wf.name)
                self.storage.save_execution(workflow_id, execution_id, execution.to_dict())
                return execution

        # Execute steps
        try:
            for step in wf.steps:
                step_result = StepResult(
                    step_name=step.action_id,
                    action_type=step.action_type.value,
                    status=ExecutionStatus.RUNNING,
                    started_at=time.time(),
                )
                execution.step_results.append(step_result)

                try:
                    result = await step.execute(execution.context)
                    step_result.result = result
                    step_result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                    step_result.finished_at = time.time()

                    # Store output in context for next steps
                    if result.success and result.output:
                        execution.context[f"_step_{step.action_id}_output"] = result.output

                    if not result.success:
                        execution.status = ExecutionStatus.FAILED
                        execution.error = result.error
                        execution.finished_at = time.time()
                        break

                except Exception as exc:
                    step_result.status = ExecutionStatus.FAILED
                    step_result.finished_at = time.time()
                    step_result.result = ActionResult(success=False, error=str(exc))
                    execution.status = ExecutionStatus.FAILED
                    execution.error = str(exc)
                    execution.finished_at = time.time()
                    break
            else:
                execution.status = ExecutionStatus.COMPLETED
                execution.finished_at = time.time()

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error = str(exc)
            execution.finished_at = time.time()

        # Save to storage
        self.storage.save_execution(workflow_id, execution_id, execution.to_dict())

        duration = (execution.finished_at - execution.started_at) * 1000
        logger.info(
            "Workflow %s execution %s: %s (%.1fms)",
            wf.name, execution_id, execution.status.value, duration,
        )

        return execution

    async def cancel(self, execution_id: str) -> bool:
        execution = self._executions.get(execution_id)
        if execution and execution.status == ExecutionStatus.RUNNING:
            execution.status = ExecutionStatus.CANCELLED
            execution.finished_at = time.time()
            return True
        return False

    # ── Stats ───────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        storage_stats = self.storage.get_stats()
        return {
            "registered_workflows": len(self._workflows),
            "active_workflows": sum(1 for w in self._workflows.values() if w.status == WorkflowStatus.ACTIVE),
            "total_executions": len(self._executions),
            "storage": storage_stats,
        }


# Module-level singleton
_engine: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
