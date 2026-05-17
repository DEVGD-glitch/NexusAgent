"""
NEXUS Rules Engine — Condition compiler and evaluator.

Compiles RuleCondition objects into callable predicates with caching,
then evaluates sets of conditions against a runtime context dictionary.
"""

from __future__ import annotations

import logging
import operator
import re
from typing import Any, Callable

from nexus.rules.rule import RuleCondition

logger = logging.getLogger(__name__)

# ── Operator mapping ────────────────────────────────────────────────────────

_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": operator.eq,
    "neq": operator.ne,
    "gt": operator.gt,
    "lt": operator.lt,
    "gte": operator.ge,
    "lte": operator.le,
}


def _resolve_field(context: dict[str, Any], field_path: str) -> Any:
    """Resolve a dotted field path against the context dict.

    Example: context = {"tool": {"name": "read"}}
             field_path = "tool.name" -> "read"
    """
    parts = field_path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)) and part.isdigit():
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        else:
            try:
                current = getattr(current, part)
            except (AttributeError, TypeError):
                return None
        if current is None:
            break
    return current


def _build_contains(
    condition: RuleCondition,
) -> Callable[[dict[str, Any]], bool]:
    """Build a 'contains' predicate (substring / membership check)."""
    def predicate(context: dict[str, Any]) -> bool:
        resolved = _resolve_field(context, condition.field)
        if resolved is None:
            return False
        try:
            return condition.value in resolved
        except TypeError:
            return False
    return predicate


def _build_matches(
    condition: RuleCondition,
) -> Callable[[dict[str, Any]], bool]:
    """Build a regex 'matches' predicate."""
    pattern = re.compile(str(condition.value))

    def predicate(context: dict[str, Any]) -> bool:
        resolved = _resolve_field(context, condition.field)
        if resolved is None:
            return False
        if isinstance(resolved, str):
            return bool(pattern.search(resolved))
        return False

    return predicate


def _build_comparator(
    condition: RuleCondition,
) -> Callable[[dict[str, Any]], bool]:
    """Build a comparator-based predicate for eq/neq/gt/lt."""
    comp = _COMPARATORS.get(condition.operator)
    if comp is None:
        raise ValueError(f"Unknown operator '{condition.operator}'")

    def predicate(context: dict[str, Any]) -> bool:
        resolved = _resolve_field(context, condition.field)
        if resolved is None:
            return False
        try:
            return comp(resolved, condition.value)
        except (TypeError, ValueError):
            return False

    return predicate


def compile_condition(condition: RuleCondition) -> Callable[[dict[str, Any]], bool]:
    """Compile a single RuleCondition into a callable predicate.

    The returned callable accepts a context dict and returns bool.
    For hot-path code with caching, use ``RuleCompiler`` instead.

    Args:
        condition: The RuleCondition to compile.

    Returns:
        A callable: context -> bool

    Raises:
        ValueError: If the operator is unknown.
    """
    op = condition.operator

    if op == "contains":
        return _build_contains(condition)
    if op == "matches":
        return _build_matches(condition)
    if op in _COMPARATORS:
        return _build_comparator(condition)

    raise ValueError(
        f"Unknown operator '{op}'. "
        f"Valid: {sorted(_COMPARATORS)} + 'contains', 'matches'"
    )


def evaluate_conditions(
    conditions: list[RuleCondition], context: dict[str, Any]
) -> bool:
    """Evaluate all conditions against the context (AND logic).

    All conditions must pass for the rule to apply. If conditions
    is empty, the result is True (unconditional rule).

    Args:
        conditions: List of RuleCondition objects.
        context: Runtime context dictionary with trigger information.

    Returns:
        True if all conditions pass (or no conditions), False otherwise.
    """
    if not conditions:
        return True

    for condition in conditions:
        predicate = compile_condition(condition)
        if not predicate(context):
            return False

    return True


# ── RuleCompiler ────────────────────────────────────────────────────────────


class RuleCompiler:
    """Compiles and caches condition predicates for efficient re-evaluation.

    Maintains a compiled cache of all conditions seen during the session,
    avoiding repeated compilation of the same condition patterns.
    Use this for hot-path evaluation where the same rules run many times.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Callable[[dict[str, Any]], bool]] = {}
        self._hits = 0
        self._misses = 0

    def compile(self, condition: RuleCondition) -> Callable[[dict[str, Any]], bool]:
        """Compile or retrieve a cached predicate for the given condition.

        Uses a compound key of field:operator:repr(value) for cache
        lookup to preserve type fidelity (int != str).
        """
        key = f"{condition.field}:{condition.operator}:{type(condition.value).__name__}:{condition.value!r}"
        cached = self._cache.get(key)
        if cached is not None:
            self._hits += 1
            return cached

        self._misses += 1
        predicate = compile_condition(condition)
        self._cache[key] = predicate
        return predicate

    def evaluate(self, conditions: list[RuleCondition], context: dict[str, Any]) -> bool:
        """Evaluate conditions using the compiled cache."""
        if not conditions:
            return True

        for condition in conditions:
            predicate = self.compile(condition)
            if not predicate(context):
                return False

        return True

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}

    def clear(self) -> None:
        """Clear the compiled condition cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._cache_stats()
        logger.debug("RuleCompiler cache cleared")

    def _cache_stats(self) -> None:
        total = self._hits + self._misses
        if total > 0:
            logger.debug(
                "RuleCompiler: %d hits, %d misses, %d cached (%.1f%% hit rate)",
                self._hits, self._misses, len(self._cache),
                100.0 * self._hits / total,
            )
