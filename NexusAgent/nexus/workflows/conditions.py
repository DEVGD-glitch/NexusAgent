"""Workflow Conditions — Boolean predicates for conditional execution."""

from __future__ import annotations

import logging
import operator
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Operator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


_OPS: dict[str, Any] = {
    "eq": operator.eq,
    "neq": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}


class Condition(ABC):
    """Base condition — evaluates to True or False."""

    @abstractmethod
    def evaluate(self, context: dict[str, Any]) -> bool: ...

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.__class__.__name__}


class SimpleCondition(Condition):
    """field <op> value"""

    def __init__(self, field: str, op: str, value: Any) -> None:
        self.field = field
        self.op = op
        self.value = value

    def evaluate(self, context: dict[str, Any]) -> bool:
        actual = context.get(self.field)

        if self.op in ("exists",):
            return actual is not None
        if self.op in ("not_exists",):
            return actual is None

        if actual is None:
            return False

        if self.op in _OPS:
            try:
                return _OPS[self.op](actual, self.value)
            except TypeError:
                return False

        if self.op == "contains":
            return self.value in str(actual)
        if self.op == "not_contains":
            return self.value not in str(actual)
        if self.op == "matches":
            return bool(re.search(str(self.value), str(actual)))
        if self.op == "in":
            return actual in self.value if isinstance(self.value, (list, tuple)) else False
        if self.op == "not_in":
            return actual not in self.value if isinstance(self.value, (list, tuple)) else True

        logger.warning("Unknown operator: %s", self.op)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "simple",
            "field": self.field,
            "op": self.op,
            "value": self.value,
        }


class AndCondition(Condition):
    """All sub-conditions must be true."""

    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def evaluate(self, context: dict[str, Any]) -> bool:
        return all(c.evaluate(context) for c in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "and",
            "conditions": [c.to_dict() for c in self.conditions],
        }


class OrCondition(Condition):
    """At least one sub-condition must be true."""

    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def evaluate(self, context: dict[str, Any]) -> bool:
        return any(c.evaluate(context) for c in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "or",
            "conditions": [c.to_dict() for c in self.conditions],
        }


class NotCondition(Condition):
    """Negates a sub-condition."""

    def __init__(self, condition: Condition) -> None:
        self.condition = condition

    def evaluate(self, context: dict[str, Any]) -> bool:
        return not self.condition.evaluate(context)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "not", "condition": self.condition.to_dict()}


class ConditionCompiler:
    """Compiles condition dicts into Condition objects."""

    @staticmethod
    def compile(data: dict[str, Any]) -> Condition:
        ctype = data.get("type", "simple")

        if ctype == "simple":
            return SimpleCondition(
                field=data["field"],
                op=data.get("op", "eq"),
                value=data.get("value"),
            )
        elif ctype == "and":
            return AndCondition(
                [ConditionCompiler.compile(c) for c in data.get("conditions", [])]
            )
        elif ctype == "or":
            return OrCondition(
                [ConditionCompiler.compile(c) for c in data.get("conditions", [])]
            )
        elif ctype == "not":
            return NotCondition(
                ConditionCompiler.compile(data.get("condition", {"type": "simple", "field": "_", "op": "eq", "value": True}))
            )
        else:
            logger.warning("Unknown condition type: %s, defaulting to always-true", ctype)
            return SimpleCondition("_always", "eq", True)
