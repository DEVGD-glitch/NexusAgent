"""
NEXUS Rules Engine — Central engine for rule loading, evaluation, and lifecycle.

``RuleEngine`` is the main entry point for the rules subsystem. It:
  - Loads rule definitions from YAML store files in a directory.
  - Registers them with the ``RuleResolver`` for scope-based resolution.
  - Evaluates rules against runtime context on each trigger event.
  - Exposes a CRUD API for dynamic rule management at runtime.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from nexus.rules.compiler import evaluate_conditions
from nexus.rules.parser import parse_rules_from_yaml, validate_rule
from nexus.rules.resolver import RuleResolver
from nexus.rules.rule import (
    OnFailAction,
    Rule,
    RuleAction,
    RuleScope,
    RuleTrigger,
)

logger = logging.getLogger(__name__)

# Default store files to load
_SYSTEM_STORE = "system.yaml"
_WORKSPACE_STORE = "workspace.yaml"

# Triggers that short-circuit on BLOCK
_BLOCKING_TRIGGERS = frozenset({
    RuleTrigger.BEFORE_TOOL,
    RuleTrigger.BEFORE_COMMIT,
    RuleTrigger.BEFORE_FILE_DELETE,
    RuleTrigger.BEFORE_AGENT_SPAWN,
})

# Triggers that are purely informational / observer
_INFORMATIONAL_TRIGGERS = frozenset({
    RuleTrigger.AFTER_TOOL,
    RuleTrigger.ON_TASK_COMPLETE,
    RuleTrigger.ON_ERROR,
})


class RuleEngine:
    """Central rules evaluation engine.

    Usage::

        engine = RuleEngine(rules_dir="nexus/rules/stores")
        await engine.initialize()
        action, matched = await engine.evaluate(
            RuleTrigger.BEFORE_TOOL,
            {"tool_name": "bash", "args": {"command": "rm -rf /"}}
        )
        if action == RuleAction.BLOCK:
            print("Operation blocked by rules")
    """

    def __init__(self, rules_dir: str = "") -> None:
        self._rules_dir = Path(rules_dir) if rules_dir else Path(__file__).parent / "stores"
        self._resolver = RuleResolver()
        self._initialized = False

    # ── Initialization ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Load all rule stores from the configured directory.

        Load order:
          1. ``system.yaml`` — system-level rules (highest priority)
          2. ``workspace.yaml`` — workspace-level rules

        Duplicate rule IDs are replaced (last loaded wins).
        """
        if self._initialized:
            logger.warning("RuleEngine.initialize() called more than once")
            return

        stores_to_load = [
            (_SYSTEM_STORE, True),
            (_WORKSPACE_STORE, False),
        ]

        total_loaded = 0
        total_errors = 0

        for store_name, required in stores_to_load:
            store_path = self._rules_dir / store_name
            if not store_path.exists():
                if required:
                    logger.warning(
                        "Required store '%s' not found at %s",
                        store_name, store_path,
                    )
                continue

            try:
                rules = parse_rules_from_yaml(str(store_path))
            except Exception as exc:
                logger.error("Failed to load store '%s': %s", store_name, exc)
                if required:
                    raise
                continue

            # Validate and register
            valid_rules = []
            for rule in rules:
                issues = validate_rule(rule)
                if issues:
                    for issue in issues:
                        logger.warning("Rule '%s' validation: %s", rule.id, issue)
                valid_rules.append(rule)

            self._resolver.register_many(valid_rules)
            total_loaded += len(valid_rules)
            logger.info(
                "Loaded %d rule(s) from %s (%d with warnings)",
                len(valid_rules), store_name, len(issues) if rules else 0,
            )

        self._initialized = True
        logger.info(
            "RuleEngine initialized: %d rule(s) loaded from %s",
            total_loaded, self._rules_dir,
        )

    # ── Evaluation ──────────────────────────────────────────────────────────

    async def evaluate(
        self,
        trigger: RuleTrigger | str,
        context: dict[str, Any] | None = None,
    ) -> tuple[RuleAction, list[Rule]]:
        """Evaluate all applicable rules for the given trigger and context.

        Resolution strategy:
          1. Collect all enabled rules whose trigger matches.
          2. Sort by scope hierarchy (SYSTEM > WORKSPACE > AGENT > SESSION),
             then by priority descending within each scope.
          3. Walk the sorted list. The **first** rule whose conditions all
             pass wins and its action is returned.
          4. If no rule matches, returns ``(ALLOW, [])`` — default allow.

        Args:
            trigger: The lifecycle event triggering this evaluation.
            context: Runtime context dict. Must contain fields that rule
                     conditions reference (e.g., ``tool_name``, ``file_path``).

        Returns:
            A tuple of ``(action, matched_rules)`` where:
              - ``action`` is the action of the first matching rule, or
                ``RuleAction.ALLOW`` if no rule matched.
              - ``matched_rules`` is a list of all rules whose conditions
                passed (useful for collecting side-effects).
        """
        ctx: dict[str, Any] = dict(context or {})
        # Normalize trigger into the context
        if isinstance(trigger, RuleTrigger):
            ctx["trigger"] = trigger.value
            trigger_enum = trigger
        else:
            ctx["trigger"] = trigger
            trigger_enum = None

        if not self._initialized:
            logger.warning("RuleEngine.evaluate() called before initialize()")
            return RuleAction.ALLOW, []

        resolved = self._resolver.resolve(ctx)
        if not resolved:
            return RuleAction.ALLOW, []

        matched_rules: list[Rule] = []
        for rule in resolved:
            # Fast trigger pre-check
            if trigger_enum is not None and rule.trigger != trigger_enum:
                continue
            if trigger_enum is None and rule.trigger.value != ctx.get("trigger"):
                continue

            # Evaluate conditions
            conditions_pass = evaluate_conditions(rule.conditions, ctx)

            if conditions_pass:
                matched_rules.append(rule)
                # First match wins for BLOCKING triggers
                if rule.action in (RuleAction.BLOCK, RuleAction.REDIRECT):
                    logger.info(
                        "Rule '%s' matched: action=%s, scope=%s",
                        rule.id, rule.action.value, rule.scope.value,
                    )
                    return rule.action, matched_rules
                # For non-blocking matches, continue collecting
                # but WARN is still actionable
                if rule.action == RuleAction.WARN:
                    logger.warning(
                        "Rule '%s' warning: %s", rule.id, rule.description,
                    )

        # If any rule matched, return the highest-priority matched action
        if matched_rules:
            action = matched_rules[0].action
            logger.debug(
                "Rule evaluation: %d match(es), action=%s",
                len(matched_rules), action.value,
            )
            return action, matched_rules

        return RuleAction.ALLOW, []

    async def check_tool_allowed(
        self, tool_name: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Convenience: check whether a tool call is allowed.

        Shorthand for::

            action, _ = await engine.evaluate(RuleTrigger.BEFORE_TOOL, {
                "tool_name": tool_name, **(context or {})
            })
            return action != RuleAction.BLOCK

        Args:
            tool_name: Name of the tool being invoked.
            context: Additional context fields.

        Returns:
            ``True`` if the tool is permitted, ``False`` if blocked.
        """
        ctx: dict[str, Any] = dict(context or {})
        ctx.setdefault("tool_name", tool_name)
        action, _ = await self.evaluate(RuleTrigger.BEFORE_TOOL, ctx)
        return action != RuleAction.BLOCK

    # ── Rule CRUD ───────────────────────────────────────────────────────────

    def add_rule(self, rule: Rule) -> None:
        """Add (or replace) a rule at runtime.

        Args:
            rule: The Rule instance to register.
        """
        self._resolver.register(rule)
        logger.info("Rule added: '%s' (scope=%s)", rule.id, rule.scope.value)

    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule by ID.

        Silently succeeds if the rule does not exist.

        Args:
            rule_id: The unique identifier of the rule to remove.
        """
        self._resolver.unregister(rule_id)
        logger.info("Rule removed: '%s'", rule_id)

    def update_rule(self, rule: Rule) -> None:
        """Update/replace an existing rule.

        Equivalent to ``remove_rule`` + ``add_rule`` in one call.
        The rule ID determines which rule is replaced.

        Args:
            rule: The updated Rule instance (same ID as the existing rule).
        """
        self._resolver.register(rule)
        logger.info("Rule updated: '%s'", rule.id)

    def get_rules(self, scope: RuleScope | None = None) -> list[Rule]:
        """Return all registered rules, optionally filtered by scope.

        Args:
            scope: If provided, only return rules at this scope level.

        Returns:
            List of Rule objects in evaluation order.
        """
        return self._resolver.get_rules(scope)

    def get_rule(self, rule_id: str) -> Rule | None:
        """Look up a single rule by ID.

        Args:
            rule_id: The unique identifier of the rule.

        Returns:
            The Rule or None if not found.
        """
        return self._resolver.get_rule(rule_id)

    # ── Persistence ─────────────────────────────────────────────────────────

    def reload_stores(self) -> None:
        """Reload all rules from the YAML store files.

        Useful when store files have been edited externally. This is
        intentionally not async — call it from a file watcher callback.
        """
        self._resolver = RuleResolver()
        self._initialized = False
        logger.info("Rule stores scheduled for reload")

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def rule_count(self) -> int:
        """Number of registered rules."""
        return self._resolver.rule_count

    @property
    def is_initialized(self) -> bool:
        """Whether the engine has been initialized."""
        return self._initialized

    # ── Debug / Introspection ───────────────────────────────────────────────

    def describe_rules(self) -> list[dict[str, Any]]:
        """Return a human-readable summary of all registered rules.

        Useful for debugging and for the /rules status endpoint.
        """
        return [
            {
                "id": r.id,
                "description": r.description,
                "scope": r.scope.value,
                "trigger": r.trigger.value,
                "action": r.action.value,
                "conditions": len(r.conditions),
                "priority": r.priority,
                "enabled": r.enabled,
            }
            for r in self._resolver.get_rules()
        ]
