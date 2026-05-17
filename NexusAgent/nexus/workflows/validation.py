"""Workflow Validation — Validates workflow definitions before execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """A single validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning


@dataclass
class ValidationResult:
    """Result of validating a workflow definition."""
    valid: bool
    errors: list[ValidationError]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [{"field": e.field, "message": e.message, "severity": e.severity} for e in self.errors],
        }


def validate_workflow(data: dict[str, Any]) -> ValidationResult:
    """Validate a workflow definition dict."""
    errors: list[ValidationError] = []

    # Required fields
    if not data.get("id"):
        errors.append(ValidationError("id", "Workflow ID is required"))
    if not data.get("name"):
        errors.append(ValidationError("name", "Workflow name is required"))

    # Steps validation
    steps = data.get("steps", [])
    if not steps:
        errors.append(ValidationError("steps", "Workflow must have at least one step", "warning"))
    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"
        if not step.get("name"):
            errors.append(ValidationError(f"{prefix}.name", "Step name is required"))
        if not step.get("action"):
            errors.append(ValidationError(f"{prefix}.action", "Step action is required"))

    # Triggers validation
    triggers = data.get("triggers", [])
    for i, trigger in enumerate(triggers):
        prefix = f"triggers[{i}]"
        ttype = trigger.get("type")
        if not ttype:
            errors.append(ValidationError(f"{prefix}.type", "Trigger type is required"))
        if ttype == "timer" and not trigger.get("interval_seconds"):
            errors.append(ValidationError(f"{prefix}.interval_seconds", "Timer trigger requires interval_seconds"))
        if ttype == "file_change" and not trigger.get("path"):
            errors.append(ValidationError(f"{prefix}.path", "File change trigger requires path"))
        if ttype == "event" and not trigger.get("event_name"):
            errors.append(ValidationError(f"{prefix}.event_name", "Event trigger requires event_name"))

    # Conditions validation
    conditions = data.get("conditions", [])
    for i, cond in enumerate(conditions):
        prefix = f"conditions[{i}]"
        ctype = cond.get("type", "simple")
        if ctype == "simple":
            if not cond.get("field"):
                errors.append(ValidationError(f"{prefix}.field", "Simple condition requires field"))
            if not cond.get("op"):
                errors.append(ValidationError(f"{prefix}.op", "Simple condition requires op"))
        elif ctype in ("and", "or"):
            if not cond.get("conditions"):
                errors.append(ValidationError(f"{prefix}.conditions", f"'{ctype}' condition requires sub-conditions"))
        elif ctype == "not":
            if not cond.get("condition"):
                errors.append(ValidationError(f"{prefix}.condition", "'not' condition requires a sub-condition"))

    return ValidationResult(valid=len(errors) == 0, errors=errors)
