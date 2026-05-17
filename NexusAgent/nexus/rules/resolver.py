"""
NEXUS Rules Engine — Rule resolver with scope hierarchy.

Resolves the applicable set of rules for a given runtime context,
enforcing the scope hierarchy: SYSTEM > WORKSPACE > AGENT > SESSION.
Within the same scope, higher-priority rules take precedence.
"""

from __future__ import annotations

import logging
from typing import Any

from nexus.rules.rule import Rule, RuleScope

logger = logging.getLogger(__name__)

# ── Scope hierarchy (lower index = higher priority) ─────────────────────────

_SCOPE_RANK: dict[RuleScope, int] = {
    RuleScope.SYSTEM: 0,
    RuleScope.WORKSPACE: 1,
    RuleScope.AGENT: 2,
    RuleScope.SESSION: 3,
}


def _scope_rank(scope: RuleScope) -> int:
    """Return the numeric rank of a scope (0 = highest priority)."""
    return _SCOPE_RANK.get(scope, 99)


# ── RuleResolver ────────────────────────────────────────────────────────────


class RuleResolver:
    """Resolves which rules apply to a given runtime context.

    Resolution strategy:
      1. Filter rules by trigger match against context.
      2. Filter out disabled rules.
      3. Sort by scope hierarchy (SYSTEM > WORKSPACE > AGENT > SESSION).
      4. Within the same scope, sort by priority (higher = first).
      5. Return in evaluation order.

    The first matching rule in the resolved list determines the action
    (short-circuit evaluation).
    """

    def __init__(self) -> None:
        self._rules: list[Rule] = []
        self._rule_map: dict[str, Rule] = {}

    @property
    def rule_count(self) -> int:
        """Return the total number of registered rules."""
        return len(self._rules)

    def register(self, rule: Rule) -> None:
        """Register a single rule.

        Replaces any existing rule with the same ID.
        """
        self._rule_map[rule.id] = rule
        self._rebuild_index()
        logger.debug("Registered rule '%s' (scope=%s, priority=%d)", rule.id, rule.scope.value, rule.priority)

    def register_many(self, rules: list[Rule]) -> None:
        """Register multiple rules at once.

        More efficient than calling register() in a loop.
        """
        for rule in rules:
            self._rule_map[rule.id] = rule
        self._rebuild_index()
        logger.debug("Registered %d rule(s)", len(rules))

    def unregister(self, rule_id: str) -> None:
        """Remove a rule by ID.

        Silently succeeds if the rule does not exist.
        """
        if rule_id in self._rule_map:
            del self._rule_map[rule_id]
            self._rebuild_index()
            logger.debug("Unregistered rule '%s'", rule_id)

    def get_rule(self, rule_id: str) -> Rule | None:
        """Look up a rule by ID."""
        return self._rule_map.get(rule_id)

    def get_rules(self, scope: RuleScope | None = None) -> list[Rule]:
        """Return registered rules, optionally filtered by scope."""
        if scope is None:
            return list(self._rules)
        return [r for r in self._rules if r.scope == scope]

    def _rebuild_index(self) -> None:
        """Rebuild the sorted rule list from the rule map."""
        self._rules = sorted(
            self._rule_map.values(),
            key=lambda r: (_scope_rank(r.scope), -r.priority),
        )

    def resolve(
        self, context: dict[str, Any], rules: list[Rule] | None = None
    ) -> list[Rule]:
        """Resolve applicable rules for the given context.

        Returns rules sorted in evaluation order (highest priority first).
        Only enabled rules whose trigger matches the context are included.

        Args:
            context: Runtime context dict. Must include at least ``trigger``.
            rules: Optional subset of rules to consider. If None, uses all
                   registered rules.

        Returns:
            List of matching Rule objects in evaluation order.
        """
        candidates = rules if rules is not None else self._rules
        trigger = context.get("trigger")

        matching: list[Rule] = []
        for rule in candidates:
            if not rule.enabled:
                continue
            if trigger is not None:
                rule_trigger = rule.trigger.value if hasattr(rule.trigger, "value") else rule.trigger
                if isinstance(trigger, str):
                    if rule_trigger != trigger:
                        continue
                else:
                    # trigger is a RuleTrigger enum
                    if rule.trigger != trigger:
                        continue
            matching.append(rule)

        # Sort: scope hierarchy first, then priority descending
        matching.sort(
            key=lambda r: (_scope_rank(r.scope), -r.priority)
        )

        return matching

    def resolve_for_scope(
        self, scope: RuleScope, context: dict[str, Any]
    ) -> list[Rule]:
        """Resolve rules for a specific scope only.

        Useful for workspace-level overrides that should not affect
        system-level rules.

        Args:
            scope: Only consider rules at this scope level.
            context: Runtime context dict.

        Returns:
            List of matching Rule objects at the given scope.
        """
        scoped = [r for r in self._rules if r.scope == scope]
        return self.resolve(context, rules=scoped)
