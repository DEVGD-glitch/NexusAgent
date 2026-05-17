"""
NEXUS Rules Engine — comprehensive test suite.

Tests cover:
  - Rule model creation and validation
  - YAML parsing and validation
  - Condition compilation and evaluation (all operators)
  - RuleCompiler caching
  - RuleResolver scope hierarchy
  - RuleEngine initialization, evaluation, CRUD
  - System YAML store loading
  - Edge cases: empty conditions, missing fields, invalid regex
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nexus.rules import (
    OnFailAction,
    Rule,
    RuleAction,
    RuleCondition,
    RuleEffect,
    RuleEffectType,
    RuleEngine,
    RuleScope,
    RuleTrigger,
)
from nexus.rules.compiler import (
    RuleCompiler,
    compile_condition,
    evaluate_conditions,
)
from nexus.rules.parser import parse_rule, parse_rules_from_yaml, validate_rule
from nexus.rules.resolver import RuleResolver

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def stores_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "nexus" / "rules" / "stores"


@pytest.fixture
def sample_rule() -> Rule:
    return Rule(
        id="test_block_bash",
        description="Block all bash tool calls",
        scope=RuleScope.WORKSPACE,
        trigger=RuleTrigger.BEFORE_TOOL,
        conditions=[RuleCondition(field="tool_name", operator="eq", value="bash")],
        action=RuleAction.BLOCK,
        on_fail=OnFailAction.BLOCK,
        priority=50,
    )


@pytest.fixture
def sample_rule_dict() -> dict:
    return {
        "id": "parsed_rule",
        "description": "Parsed from dict",
        "scope": "system",
        "trigger": "before_file_delete",
        "conditions": [{"field": "file_path", "operator": "matches", "value": r".*\.env"}],
        "action": "block",
        "on_fail": "block",
        "priority": 100,
    }


@pytest.fixture
def engine() -> RuleEngine:
    eng = RuleEngine()
    return eng


# ── Rule Model Tests ────────────────────────────────────────────────────────


class TestRuleModel:
    def test_create_minimal_rule(self):
        rule = Rule(id="minimal", trigger=RuleTrigger.BEFORE_TOOL)
        assert rule.id == "minimal"
        assert rule.scope == RuleScope.WORKSPACE
        assert rule.action == RuleAction.ALLOW
        assert rule.priority == 0
        assert rule.enabled is True
        assert rule.conditions == []
        assert rule.effects == []

    def test_create_full_rule(self):
        rule = Rule(
            id="full",
            description="Full rule",
            scope=RuleScope.SYSTEM,
            trigger=RuleTrigger.BEFORE_FILE_DELETE,
            conditions=[RuleCondition(field="path", operator="eq", value="/etc")],
            action=RuleAction.BLOCK,
            effects=[RuleEffect(type=RuleEffectType.ADD_CONTEXT, value={"reason": "protected"})],
            on_fail=OnFailAction.WARN,
            priority=100,
            enabled=False,
        )
        assert rule.scope == RuleScope.SYSTEM
        assert rule.action == RuleAction.BLOCK
        assert len(rule.effects) == 1

    def test_applies_to_trigger_match(self):
        rule = Rule(id="t", trigger=RuleTrigger.BEFORE_TOOL)
        assert rule.applies_to({"trigger": "before_tool"}) is True
        assert rule.applies_to({"trigger": RuleTrigger.BEFORE_TOOL}) is True

    def test_applies_to_trigger_mismatch(self):
        rule = Rule(id="t", trigger=RuleTrigger.BEFORE_TOOL)
        assert rule.applies_to({"trigger": "on_task_start"}) is False

    def test_rule_equality_by_id(self):
        a = Rule(id="same", trigger=RuleTrigger.BEFORE_TOOL)
        b = Rule(id="same", trigger=RuleTrigger.AFTER_TOOL)
        assert a == b

    def test_rule_roundtrip_serialization(self):
        rule = Rule(
            id="serialize_test",
            description="Test",
            scope=RuleScope.SYSTEM,
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="x", operator="eq", value=42)],
            action=RuleAction.BLOCK,
            priority=10,
        )
        dumped = rule.model_dump(mode="json")
        assert dumped["id"] == "serialize_test"
        assert dumped["scope"] == "system"
        assert dumped["trigger"] == "before_tool"
        assert dumped["conditions"][0]["field"] == "x"
        assert dumped["conditions"][0]["value"] == 42

        restored = Rule.model_validate(dumped)
        assert restored.id == rule.id
        assert restored.conditions[0].value == 42


# ── Parser Tests ────────────────────────────────────────────────────────────


class TestParser:
    def test_parse_rule(self, sample_rule_dict):
        rule = parse_rule(sample_rule_dict)
        assert rule.id == "parsed_rule"
        assert rule.scope == RuleScope.SYSTEM
        assert rule.trigger == RuleTrigger.BEFORE_FILE_DELETE
        assert rule.action == RuleAction.BLOCK
        assert len(rule.conditions) == 1

    def test_parse_rule_missing_id(self):
        with pytest.raises(ValueError, match="missing required 'id'"):
            parse_rule({"trigger": "before_tool"})

    def test_parse_rule_invalid_scope(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            parse_rule({"id": "bad", "trigger": "before_tool", "scope": "nope"})

    def test_parse_rule_invalid_trigger(self):
        with pytest.raises(ValueError, match="Invalid trigger"):
            parse_rule({"id": "bad", "trigger": "never_happens"})

    def test_parse_rule_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid action"):
            parse_rule({"id": "bad", "trigger": "before_tool", "action": "nuke"})

    def test_parse_rule_invalid_operator(self):
        with pytest.raises(ValueError, match="Invalid operator"):
            parse_rule({
                "id": "bad",
                "trigger": "before_tool",
                "conditions": [{"field": "x", "operator": "bad_op", "value": 1}],
            })

    def test_parse_rule_defaults(self):
        rule = parse_rule({"id": "minimal", "trigger": "before_tool"})
        assert rule.scope == RuleScope.WORKSPACE
        assert rule.action == RuleAction.ALLOW
        assert rule.on_fail == OnFailAction.BLOCK
        assert rule.priority == 0
        assert rule.enabled is True

    def test_parse_rules_from_yaml(self, stores_dir):
        path = stores_dir / "system.yaml"
        rules = parse_rules_from_yaml(str(path))
        assert len(rules) > 0
        ids = {r.id for r in rules}
        assert "system_no_destructive_without_confirm" in ids
        assert "system_no_dangerous_commands" in ids

    def test_validate_rule_regex(self):
        rule = Rule(
            id="bad_regex",
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="x", operator="matches", value=r"[invalid")],
        )
        issues = validate_rule(rule)
        assert len(issues) > 0
        assert "invalid regex" in issues[0]

    def test_validate_rule_no_conditions(self):
        rule = Rule(
            id="no_conds",
            trigger=RuleTrigger.BEFORE_FILE_DELETE,
        )
        issues = validate_rule(rule)
        assert len(issues) > 0


# ── Compiler Tests ──────────────────────────────────────────────────────────


class TestCompiler:
    def test_eq_operator(self):
        pred = compile_condition(RuleCondition(field="name", operator="eq", value="foo"))
        assert pred({"name": "foo"}) is True
        assert pred({"name": "bar"}) is False

    def test_neq_operator(self):
        pred = compile_condition(RuleCondition(field="name", operator="neq", value="foo"))
        assert pred({"name": "bar"}) is True
        assert pred({"name": "foo"}) is False

    def test_gt_operator(self):
        pred = compile_condition(RuleCondition(field="count", operator="gt", value=5))
        assert pred({"count": 10}) is True
        assert pred({"count": 5}) is False
        assert pred({"count": 3}) is False

    def test_lt_operator(self):
        pred = compile_condition(RuleCondition(field="count", operator="lt", value=5))
        assert pred({"count": 3}) is True
        assert pred({"count": 5}) is False

    def test_gte_operator(self):
        pred = compile_condition(RuleCondition(field="count", operator="gte", value=5))
        assert pred({"count": 5}) is True
        assert pred({"count": 10}) is True
        assert pred({"count": 3}) is False

    def test_lte_operator(self):
        pred = compile_condition(RuleCondition(field="count", operator="lte", value=5))
        assert pred({"count": 5}) is True
        assert pred({"count": 3}) is True
        assert pred({"count": 10}) is False

    def test_contains_operator_string(self):
        pred = compile_condition(RuleCondition(field="command", operator="contains", value="rm -rf"))
        assert pred({"command": "rm -rf /"}) is True
        assert pred({"command": "ls -la"}) is False

    def test_contains_operator_list(self):
        pred = compile_condition(RuleCondition(field="tags", operator="contains", value="critical"))
        assert pred({"tags": ["safe", "critical", "urgent"]}) is True
        assert pred({"tags": ["safe", "normal"]}) is False

    def test_matches_operator(self):
        pred = compile_condition(RuleCondition(field="path", operator="matches", value=r".*\.py$"))
        assert pred({"path": "main.py"}) is True
        assert pred({"path": "main.pyc"}) is False
        assert pred({"path": "main.txt"}) is False

    def test_dotted_field_resolution(self):
        pred = compile_condition(RuleCondition(field="args.command", operator="contains", value="rm"))
        assert pred({"args": {"command": "rm -rf /"}}) is True
        assert pred({"args": {"command": "ls"}}) is False

    def test_none_field_resolves_false(self):
        pred = compile_condition(RuleCondition(field="missing.field", operator="eq", value="x"))
        assert pred({}) is False

    def test_unknown_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            compile_condition(RuleCondition(field="x", operator="bogus", value=1))

    def test_evaluate_conditions_all_pass(self):
        conds = [
            RuleCondition(field="a", operator="eq", value=1),
            RuleCondition(field="b", operator="eq", value=2),
        ]
        assert evaluate_conditions(conds, {"a": 1, "b": 2}) is True

    def test_evaluate_conditions_one_fails(self):
        conds = [
            RuleCondition(field="a", operator="eq", value=1),
            RuleCondition(field="b", operator="eq", value=99),
        ]
        assert evaluate_conditions(conds, {"a": 1, "b": 2}) is False

    def test_evaluate_conditions_empty(self):
        assert evaluate_conditions([], {"anything": "goes"}) is True

    def test_rulecompiler_cache(self):
        compiler = RuleCompiler()
        cond = RuleCondition(field="tool", operator="eq", value="bash")

        # First call: miss
        r1 = compiler.evaluate([cond], {"tool": "bash"})
        assert r1 is True
        assert compiler.stats["misses"] == 1

        # Same condition again: hit
        r2 = compiler.evaluate([cond], {"tool": "python"})
        assert r2 is False
        assert compiler.stats["hits"] >= 1

        compiler.clear()
        assert compiler.stats["size"] == 0


# ── Resolver Tests ──────────────────────────────────────────────────────────


class TestResolver:
    def test_resolve_no_rules(self):
        resolver = RuleResolver()
        assert resolver.resolve({"trigger": "before_tool"}) == []

    def test_resolve_by_trigger(self, sample_rule):
        resolver = RuleResolver()
        resolver.register(sample_rule)
        resolved = resolver.resolve({"trigger": "before_tool"})
        assert len(resolved) == 1
        assert resolved[0].id == "test_block_bash"

    def test_resolve_wrong_trigger(self, sample_rule):
        resolver = RuleResolver()
        resolver.register(sample_rule)
        resolved = resolver.resolve({"trigger": "on_task_start"})
        assert len(resolved) == 0

    def test_resolve_disabled_rule(self):
        rule = Rule(id="disabled", trigger=RuleTrigger.BEFORE_TOOL, enabled=False)
        resolver = RuleResolver()
        resolver.register(rule)
        resolved = resolver.resolve({"trigger": "before_tool"})
        assert len(resolved) == 0

    def test_scope_hierarchy(self):
        rules = [
            Rule(id="session_rule", scope=RuleScope.SESSION, trigger=RuleTrigger.BEFORE_TOOL, priority=0),
            Rule(id="agent_rule", scope=RuleScope.AGENT, trigger=RuleTrigger.BEFORE_TOOL, priority=0),
            Rule(id="workspace_rule", scope=RuleScope.WORKSPACE, trigger=RuleTrigger.BEFORE_TOOL, priority=0),
            Rule(id="system_rule", scope=RuleScope.SYSTEM, trigger=RuleTrigger.BEFORE_TOOL, priority=0),
        ]
        resolver = RuleResolver()
        resolver.register_many(rules)
        resolved = resolver.resolve({"trigger": "before_tool"})
        ids = [r.id for r in resolved]
        # System first, then workspace, then agent, then session
        assert ids.index("system_rule") < ids.index("workspace_rule")
        assert ids.index("workspace_rule") < ids.index("agent_rule")
        assert ids.index("agent_rule") < ids.index("session_rule")

    def test_priority_within_scope(self):
        rules = [
            Rule(id="low", scope=RuleScope.WORKSPACE, trigger=RuleTrigger.BEFORE_TOOL, priority=10),
            Rule(id="high", scope=RuleScope.WORKSPACE, trigger=RuleTrigger.BEFORE_TOOL, priority=100),
        ]
        resolver = RuleResolver()
        resolver.register_many(rules)
        resolved = resolver.resolve({"trigger": "before_tool"})
        assert resolved[0].id == "high"
        assert resolved[1].id == "low"

    def test_system_overrides_workspace(self):
        rules = [
            Rule(id="ws_allow", scope=RuleScope.WORKSPACE, trigger=RuleTrigger.BEFORE_TOOL, action=RuleAction.ALLOW, priority=100),
            Rule(id="sys_block", scope=RuleScope.SYSTEM, trigger=RuleTrigger.BEFORE_TOOL, action=RuleAction.BLOCK, priority=1),
        ]
        resolver = RuleResolver()
        resolver.register_many(rules)
        resolved = resolver.resolve({"trigger": "before_tool"})
        assert resolved[0].id == "sys_block"
        assert resolved[1].id == "ws_allow"

    def test_get_rule(self, sample_rule):
        resolver = RuleResolver()
        resolver.register(sample_rule)
        assert resolver.get_rule("test_block_bash") is not None
        assert resolver.get_rule("nonexistent") is None

    def test_unregister(self, sample_rule):
        resolver = RuleResolver()
        resolver.register(sample_rule)
        assert resolver.rule_count == 1
        resolver.unregister("test_block_bash")
        assert resolver.rule_count == 0
        # Unregister non-existent is silent
        resolver.unregister("nonexistent")

    def test_get_rules_by_scope(self):
        rules = [
            Rule(id="s1", scope=RuleScope.SYSTEM, trigger=RuleTrigger.BEFORE_TOOL),
            Rule(id="s2", scope=RuleScope.SYSTEM, trigger=RuleTrigger.BEFORE_TOOL),
            Rule(id="w1", scope=RuleScope.WORKSPACE, trigger=RuleTrigger.BEFORE_TOOL),
        ]
        resolver = RuleResolver()
        resolver.register_many(rules)
        system_rules = resolver.get_rules(RuleScope.SYSTEM)
        assert len(system_rules) == 2
        assert resolver.get_rules(RuleScope.SESSION) == []


# ── Engine Tests ────────────────────────────────────────────────────────────


class TestRuleEngine:
    async def test_initialize_loads_stores(self, engine):
        await engine.initialize()
        assert engine.is_initialized is True
        assert engine.rule_count > 0

    async def test_initialize_idempotent(self, engine):
        await engine.initialize()
        count = engine.rule_count
        await engine.initialize()  # second call
        assert engine.rule_count == count

    async def test_add_rule(self, engine, sample_rule):
        await engine.initialize()
        count = engine.rule_count
        engine.add_rule(sample_rule)
        assert engine.rule_count == count + 1
        assert engine.get_rule("test_block_bash") is not None

    async def test_remove_rule(self, engine, sample_rule):
        await engine.initialize()
        engine.add_rule(sample_rule)
        engine.remove_rule("test_block_bash")
        assert engine.get_rule("test_block_bash") is None

    async def test_update_rule(self, engine):
        await engine.initialize()
        rule = Rule(id="update_test", trigger=RuleTrigger.BEFORE_TOOL, action=RuleAction.ALLOW)
        engine.add_rule(rule)
        updated = Rule(id="update_test", trigger=RuleTrigger.BEFORE_TOOL, action=RuleAction.BLOCK)
        engine.update_rule(updated)
        fetched = engine.get_rule("update_test")
        assert fetched is not None
        assert fetched.action == RuleAction.BLOCK

    async def test_evaluate_block(self, engine):
        await engine.initialize()
        rule = Rule(
            id="block_python",
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="tool_name", operator="eq", value="python")],
            action=RuleAction.BLOCK,
            priority=100,
        )
        engine.add_rule(rule)

        action, matched = await engine.evaluate(RuleTrigger.BEFORE_TOOL, {"tool_name": "python"})
        assert action == RuleAction.BLOCK
        assert len(matched) >= 1

    async def test_evaluate_allow_default(self, engine):
        await engine.initialize()
        # nonexistent_tool matches no conditional rules; system_always_log_tool_calls
        # matches unconditionally with action=ALLOW
        action, matched = await engine.evaluate(RuleTrigger.BEFORE_TOOL, {"tool_name": "nonexistent_tool"})
        assert action == RuleAction.ALLOW
        # At least the unconditional system rule should match
        assert len(matched) > 0

    async def test_evaluate_warn(self, tmp_path):
        # Engine with an empty stores directory — no pre-loaded system rules
        empty_stores = tmp_path / "empty_stores"
        empty_stores.mkdir()
        # Create empty store files so initialize() doesn't warn
        for f in ("system.yaml", "workspace.yaml"):
            (empty_stores / f).write_text("rules: []")
        engine = RuleEngine(rules_dir=str(empty_stores))
        await engine.initialize()
        rule = Rule(
            id="warn_network",
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="tool_name", operator="eq", value="network")],
            action=RuleAction.WARN,
            priority=50,
        )
        engine.add_rule(rule)

        action, matched = await engine.evaluate(RuleTrigger.BEFORE_TOOL, {"tool_name": "network"})
        assert action == RuleAction.WARN
        assert len(matched) >= 1

    async def test_check_tool_allowed_blocked(self, engine):
        await engine.initialize()
        rule = Rule(
            id="block_bash_tool",
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="tool_name", operator="eq", value="bash")],
            action=RuleAction.BLOCK,
        )
        engine.add_rule(rule)
        allowed = await engine.check_tool_allowed("bash", {"args": {"command": "ls"}})
        assert allowed is False

    async def test_check_tool_allowed_permitted(self, engine):
        await engine.initialize()
        allowed = await engine.check_tool_allowed("safe_tool")
        assert allowed is True

    async def test_get_rules_filtered(self, engine):
        await engine.initialize()
        # Add a session rule
        engine.add_rule(
            Rule(id="session_only", scope=RuleScope.SESSION, trigger=RuleTrigger.BEFORE_TOOL)
        )
        system_rules = engine.get_rules(RuleScope.SYSTEM)
        assert len(system_rules) > 0
        session_rules = engine.get_rules(RuleScope.SESSION)
        assert len(session_rules) == 1

    async def test_describe_rules(self, engine):
        await engine.initialize()
        desc = engine.describe_rules()
        assert len(desc) > 0
        keys = {"id", "scope", "trigger", "action", "conditions", "priority", "enabled"}
        for entry in desc:
            assert keys.issubset(entry.keys())

    async def test_evaluate_with_string_trigger(self, engine):
        await engine.initialize()
        rule = Rule(
            id="str_trigger_test",
            trigger=RuleTrigger.BEFORE_TOOL,
            conditions=[RuleCondition(field="tool_name", operator="eq", value="test_tool")],
            action=RuleAction.BLOCK,
        )
        engine.add_rule(rule)
        action, matched = await engine.evaluate("before_tool", {"tool_name": "test_tool"})
        assert action == RuleAction.BLOCK

    async def test_system_rules_override(self, engine):
        """System-level rules should override workspace-level ones."""
        await engine.initialize()
        engine.add_rule(
            Rule(
                id="workspace_allow_rm",
                scope=RuleScope.WORKSPACE,
                trigger=RuleTrigger.BEFORE_FILE_DELETE,
                action=RuleAction.ALLOW,
                priority=100,
            )
        )
        # The system rule system_no_destructive_without_confirm should still apply
        action, matched = await engine.evaluate(
            RuleTrigger.BEFORE_FILE_DELETE,
            {"file_path": "/important/data"},
        )
        # System rule has higher scope, so BLOCK wins
        assert action == RuleAction.BLOCK

    async def test_dangerous_command_detection(self, engine):
        """system_no_dangerous_commands should block dangerous patterns."""
        await engine.initialize()
        action, _ = await engine.evaluate(
            RuleTrigger.BEFORE_TOOL,
            {"tool_name": "bash", "args": {"command": "rm -rf /"}},
        )
        assert action == RuleAction.BLOCK

        action2, _ = await engine.evaluate(
            RuleTrigger.BEFORE_TOOL,
            {"tool_name": "bash", "args": {"command": "ls -la"}},
        )
        assert action2 == RuleAction.ALLOW

    async def test_evaluate_no_initialization(self):
        """Evaluating without calling initialize() should log and be safe."""
        engine = RuleEngine()
        action, matched = await engine.evaluate(RuleTrigger.BEFORE_TOOL, {})
        assert action == RuleAction.ALLOW
        assert len(matched) == 0
