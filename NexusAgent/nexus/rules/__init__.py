"""
NEXUS Rules Engine — Declarative, hierarchical rule system.

The Rules Engine provides a YAML-driven, event-triggered rule evaluation
system that governs NEXUS agent behaviour across all lifecycle events.
Rules are organised into a scope hierarchy (SYSTEM > WORKSPACE > AGENT > SESSION)
and can BLOCK, WARN, ALLOW, REDIRECT, MODIFY, or RUN_WORKFLOW in response
to tool calls, task events, commits, file operations, and agent spawning.

Quick start::

    from nexus.rules import RuleEngine

    engine = RuleEngine("nexus/rules/stores")
    await engine.initialize()
    action, rules = await engine.evaluate("before_tool", {
        "tool_name": "bash",
        "args": {"command": "rm -rf /"},
    })
    if action == RuleAction.BLOCK:
        print("Blocked by rules!")
"""

from __future__ import annotations

from nexus.rules.engine import RuleEngine
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

__all__ = [
    "RuleEngine",
    "Rule",
    "RuleScope",
    "RuleTrigger",
    "RuleAction",
    "OnFailAction",
    "RuleCondition",
    "RuleEffect",
    "RuleEffectType",
]
