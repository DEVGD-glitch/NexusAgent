"""
NEXUS Rules Engine — YAML parser and rule validator.

Handles deserialization of rules from YAML dictionaries and files,
including schema validation and error reporting with context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from nexus.rules.rule import (
    OnFailAction,
    Rule,
    RuleAction,
    RuleCondition,
    RuleEffect,
    RuleEffectType,
    RuleScope,
    RuleTrigger,
)

logger = logging.getLogger(__name__)

# ── Validation constants ───────────────────────────────────────────────────

VALID_OPERATORS = frozenset({"eq", "neq", "contains", "gt", "gte", "lt", "lte", "matches"})

SCOPE_MAP: dict[str, RuleScope] = {s.value: s for s in RuleScope}
TRIGGER_MAP: dict[str, RuleTrigger] = {t.value: t for t in RuleTrigger}
ACTION_MAP: dict[str, RuleAction] = {a.value: a for a in RuleAction}
ON_FAIL_MAP: dict[str, OnFailAction] = {f.value: f for f in OnFailAction}
EFFECT_TYPE_MAP: dict[str, RuleEffectType] = {e.value: e for e in RuleEffectType}


# ── Parsing ─────────────────────────────────────────────────────────────────


def _parse_scope(raw: Any) -> RuleScope:
    """Parse a scope value, raising a clear error on invalid input."""
    if isinstance(raw, RuleScope):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in SCOPE_MAP:
            return SCOPE_MAP[key]
        raise ValueError(f"Invalid scope '{raw}'. Valid: {list(SCOPE_MAP)}")
    raise TypeError(f"Scope must be str or RuleScope, got {type(raw).__name__}")


def _parse_trigger(raw: Any) -> RuleTrigger:
    """Parse a trigger value."""
    if isinstance(raw, RuleTrigger):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in TRIGGER_MAP:
            return TRIGGER_MAP[key]
        raise ValueError(f"Invalid trigger '{raw}'. Valid: {list(TRIGGER_MAP)}")
    raise TypeError(f"Trigger must be str or RuleTrigger, got {type(raw).__name__}")


def _parse_action(raw: Any) -> RuleAction:
    """Parse an action value."""
    if isinstance(raw, RuleAction):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in ACTION_MAP:
            return ACTION_MAP[key]
        raise ValueError(f"Invalid action '{raw}'. Valid: {list(ACTION_MAP)}")
    raise TypeError(f"Action must be str or RuleAction, got {type(raw).__name__}")


def _parse_on_fail(raw: Any) -> OnFailAction:
    """Parse an on_fail value."""
    if isinstance(raw, OnFailAction):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in ON_FAIL_MAP:
            return ON_FAIL_MAP[key]
        raise ValueError(f"Invalid on_fail '{raw}'. Valid: {list(ON_FAIL_MAP)}")
    raise TypeError(f"OnFailAction must be str or OnFailAction, got {type(raw).__name__}")


def _parse_effect(raw: dict[str, Any]) -> RuleEffect:
    """Parse a single effect dictionary into a RuleEffect."""
    effect_type_raw = raw.get("type")
    if not effect_type_raw:
        raise ValueError("Effect is missing required 'type' field")

    if isinstance(effect_type_raw, RuleEffectType):
        effect_type = effect_type_raw
    elif isinstance(effect_type_raw, str):
        key = effect_type_raw.strip().lower()
        if key in EFFECT_TYPE_MAP:
            effect_type = EFFECT_TYPE_MAP[key]
        else:
            raise ValueError(
                f"Invalid effect type '{effect_type_raw}'. Valid: {list(EFFECT_TYPE_MAP)}"
            )
    else:
        raise TypeError(
            f"Effect type must be str or RuleEffectType, got {type(effect_type_raw).__name__}"
        )

    return RuleEffect(type=effect_type, value=raw.get("value"))


def _parse_condition(raw: dict[str, Any]) -> RuleCondition:
    """Parse a single condition dictionary into a RuleCondition."""
    field = raw.get("field")
    if not field:
        raise ValueError("Condition is missing required 'field'")

    operator = raw.get("operator", "eq")
    if operator not in VALID_OPERATORS:
        raise ValueError(
            f"Invalid operator '{operator}' in condition for field '{field}'. "
            f"Valid: {sorted(VALID_OPERATORS)}"
        )

    return RuleCondition(field=field, operator=operator, value=raw.get("value"))


def parse_rule(data: dict[str, Any]) -> Rule:
    """Parse a raw dictionary into a validated Rule object.

    Args:
        data: Dictionary with rule fields (typically from YAML).

    Returns:
        A validated Rule instance.

    Raises:
        ValueError: If required fields are missing or values are invalid.
    """
    rule_id = data.get("id")
    if not rule_id:
        raise ValueError("Rule is missing required 'id' field")

    try:
        scope = _parse_scope(data.get("scope", "workspace"))
        trigger = _parse_trigger(data.get("trigger"))
        action = _parse_action(data.get("action", "allow"))
        on_fail = _parse_on_fail(data.get("on_fail", "block"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Rule '{rule_id}': {exc}") from exc

    # Parse conditions
    conditions: list[RuleCondition] = []
    raw_conditions = data.get("conditions", [])
    if not isinstance(raw_conditions, list):
        raise ValueError(f"Rule '{rule_id}': 'conditions' must be a list")
    for i, raw_cond in enumerate(raw_conditions):
        if not isinstance(raw_cond, dict):
            raise ValueError(
                f"Rule '{rule_id}': condition at index {i} must be a dict"
            )
        try:
            conditions.append(_parse_condition(raw_cond))
        except ValueError as exc:
            raise ValueError(f"Rule '{rule_id}': condition[{i}]: {exc}") from exc

    # Parse effects
    effects: list[RuleEffect] = []
    raw_effects = data.get("effects", [])
    if not isinstance(raw_effects, list):
        raise ValueError(f"Rule '{rule_id}': 'effects' must be a list")
    for i, raw_effect in enumerate(raw_effects):
        if not isinstance(raw_effect, dict):
            raise ValueError(
                f"Rule '{rule_id}': effect at index {i} must be a dict"
            )
        try:
            effects.append(_parse_effect(raw_effect))
        except ValueError as exc:
            raise ValueError(f"Rule '{rule_id}': effect[{i}]: {exc}") from exc

    return Rule(
        id=rule_id,
        description=data.get("description", ""),
        scope=scope,
        trigger=trigger,
        conditions=conditions,
        action=action,
        effects=effects,
        on_fail=on_fail,
        priority=int(data.get("priority", 0)),
        enabled=bool(data.get("enabled", True)),
    )


def parse_rules_from_yaml(path: str | Path) -> list[Rule]:
    """Load and parse all rules from a YAML file.

    Expected structure:
        rules:
          - id: my_rule
            description: ...
            ...

    Args:
        path: Filesystem path to a .yaml file.

    Returns:
        List of validated Rule objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        ValueError: If the parsed structure is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")

    logger.debug("Loading rules from %s", path)

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        logger.info("Empty rules file: %s", path)
        return []

    if not isinstance(raw, dict):
        raise ValueError(f"YAML root must be a mapping, got {type(raw).__name__}")

    rules_data = raw.get("rules", [])
    if not isinstance(rules_data, list):
        raise ValueError("Top-level 'rules' key must contain a list")

    rules: list[Rule] = []
    errors: list[str] = []
    for i, entry in enumerate(rules_data):
        if not isinstance(entry, dict):
            errors.append(f"rules[{i}]: expected dict, got {type(entry).__name__}")
            continue
        try:
            rule = parse_rule(entry)
            rules.append(rule)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        for err in errors:
            logger.warning("Rule parse error: %s", err)
        logger.warning(
            "Loaded %d/%d rules with %d error(s) from %s",
            len(rules),
            len(rules_data),
            len(errors),
            path,
        )

    return rules


# ── Validation ──────────────────────────────────────────────────────────────


def validate_rule(rule: Rule) -> list[str]:
    """Deep-validate a Rule's semantic correctness.

    Returns a list of validation warnings/errors (empty = valid).

    Checks performed:
      - Rule ID follows naming conventions (lowercase, no spaces).
      - Conditions are provided for non-ALWAYS triggers.
      - Operator-field compatibility.
    """
    issues: list[str] = []

    # ID conventions
    if not rule.id.islower() and not rule.id.isidentifier():
        issues.append(f"Rule ID '{rule.id}' should be lowercase identifier")

    # Trigger requires conditions for safety
    needs_conditions = {
        RuleTrigger.BEFORE_TOOL,
        RuleTrigger.AFTER_TOOL,
        RuleTrigger.BEFORE_FILE_DELETE,
        RuleTrigger.BEFORE_AGENT_SPAWN,
    }
    if rule.trigger in needs_conditions and not rule.conditions:
        issues.append(
            f"Rule '{rule.id}': trigger '{rule.trigger.value}' should have "
            f"conditions to avoid overly broad matches"
        )

    # Condition field exists check
    for i, cond in enumerate(rule.conditions):
        if cond.operator == "matches":
            import re
            try:
                re.compile(cond.value)
            except (re.error, TypeError):
                issues.append(
                    f"Rule '{rule.id}': condition[{i}] has invalid regex: {cond.value}"
                )

    return issues
