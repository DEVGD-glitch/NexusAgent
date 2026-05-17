"""
NEXUS Rules Engine — Core data models.

Defines the complete type system for the NEXUS declarative rule engine:
Rule scopes, triggers, actions, conditions, effects, and the Rule model itself.
All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────


class RuleScope(str, Enum):
    """Hierarchical scope that determines rule precedence.

    SYSTEM rules are evaluated first and override all lower scopes.
    Resolution order: SYSTEM > WORKSPACE > AGENT > SESSION.
    """

    SYSTEM = "system"
    WORKSPACE = "workspace"
    AGENT = "agent"
    SESSION = "session"


class RuleTrigger(str, Enum):
    """Lifecycle event that triggers rule evaluation."""

    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    BEFORE_COMMIT = "before_commit"
    ON_TASK_START = "on_task_start"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_ERROR = "on_error"
    BEFORE_FILE_DELETE = "before_file_delete"
    BEFORE_AGENT_SPAWN = "before_agent_spawn"


class RuleAction(str, Enum):
    """Primary action taken when a rule matches its conditions."""

    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"
    REDIRECT = "redirect"
    MODIFY = "modify"
    RUN_WORKFLOW = "run_workflow"


class OnFailAction(str, Enum):
    """Action taken when a rule evaluation fails."""

    BLOCK = "block"
    WARN = "warn"
    IGNORE = "ignore"


class RuleEffectType(str, Enum):
    """Type of side-effect a rule can produce when triggered."""

    SET_PROVIDER = "set_provider"
    SET_MODEL = "set_model"
    ADD_CONTEXT = "add_context"
    MODIFY_TOOL = "modify_tool"
    REDIRECT_TO = "redirect_to"


# ── Models ──────────────────────────────────────────────────────────────────


class RuleCondition(BaseModel):
    """A single predicate in a rule's condition set.

    All conditions in a rule are AND-ed together. For OR logic,
    create separate rules with the same action.
    """

    field: str
    operator: str  # eq, neq, contains, gt, lt, matches
    value: Any

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to ensure value is always included."""
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }


class RuleEffect(BaseModel):
    """A side-effect applied when a rule is triggered and passes conditions."""

    type: RuleEffectType
    value: Any


class Rule(BaseModel):
    """A single declarative rule in the NEXUS rules engine.

    Rules are evaluated in priority order within their scope hierarchy.
    The first matching rule (all conditions pass) determines the action.
    """

    id: str
    description: str = ""
    scope: RuleScope = RuleScope.WORKSPACE
    trigger: RuleTrigger
    conditions: list[RuleCondition] = Field(default_factory=list)
    action: RuleAction = RuleAction.ALLOW
    effects: list[RuleEffect] = Field(default_factory=list)
    on_fail: OnFailAction = OnFailAction.BLOCK
    priority: int = 0
    enabled: bool = True

    def applies_to(self, context: dict[str, Any]) -> bool:
        """Quick pre-check: is this rule relevant for the given context?

        Checks trigger match as a fast early-exit before condition evaluation.
        """
        trigger = context.get("trigger")
        if trigger is not None and isinstance(trigger, RuleTrigger):
            return trigger == self.trigger
        if trigger is not None and isinstance(trigger, str):
            return trigger == self.trigger.value
        return True

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rule):
            return self.id == other.id
        return NotImplemented
