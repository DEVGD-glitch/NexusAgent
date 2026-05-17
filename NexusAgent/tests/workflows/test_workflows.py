"""Tests for the Workflow Engine (triggers, conditions, actions, engine)."""

import pytest
import asyncio
from nexus.workflows.triggers import (
    Trigger, TriggerType, TriggerContext, TriggerFactory,
    TimerTrigger, FileChangeTrigger, WebhookTrigger, EventTrigger, ManualTrigger,
)
from nexus.workflows.conditions import (
    Condition, SimpleCondition, AndCondition, OrCondition, NotCondition, ConditionCompiler,
)
from nexus.workflows.actions import (
    Action, ActionType, ActionResult, ActionFactory,
    ToolCallAction, LLMCallAction, NotifyAction, DelayAction, SetVariableAction, ParallelAction,
)
from nexus.workflows.validation import validate_workflow, ValidationResult
from nexus.workflows.storage import WorkflowStorage
from nexus.workflows.engine import (
    WorkflowEngine, WorkflowDefinition, WorkflowExecution,
    WorkflowStatus, ExecutionStatus, get_workflow_engine,
)


# ── Triggers ───────────────────────────────────────────────────

class TestTriggers:
    def test_manual_trigger(self):
        t = ManualTrigger("test-manual")
        assert t.trigger_type == TriggerType.MANUAL
        assert t.trigger_id == "test-manual"

    def test_timer_trigger_create(self):
        t = TimerTrigger("t1", interval_seconds=5.0)
        assert t.interval == 5.0
        assert t.trigger_type == TriggerType.TIMER

    def test_webhook_trigger_create(self):
        t = WebhookTrigger("w1", path="/hook")
        assert t.webhook_path == "/hook"

    def test_event_trigger_create(self):
        t = EventTrigger("e1", event_name="file_created")
        assert t.event_name == "file_created"

    def test_trigger_factory(self):
        t = TriggerFactory.create({"type": "timer", "id": "tf1", "interval_seconds": 10})
        assert isinstance(t, TimerTrigger)
        assert t.interval == 10

    def test_trigger_factory_manual(self):
        t = TriggerFactory.create({"type": "manual", "id": "m1"})
        assert isinstance(t, ManualTrigger)

    def test_trigger_context(self):
        ctx = TriggerContext(
            trigger_type=TriggerType.MANUAL,
            trigger_id="t1",
            timestamp=1234567890.0,
            data={"key": "val"},
        )
        assert ctx.trigger_type == TriggerType.MANUAL
        assert ctx.data["key"] == "val"


# ── Conditions ─────────────────────────────────────────────────

class TestConditions:
    def test_simple_eq(self):
        c = SimpleCondition("status", "eq", "active")
        assert c.evaluate({"status": "active"}) is True
        assert c.evaluate({"status": "inactive"}) is False

    def test_simple_neq(self):
        c = SimpleCondition("x", "neq", 5)
        assert c.evaluate({"x": 3}) is True
        assert c.evaluate({"x": 5}) is False

    def test_simple_gt(self):
        c = SimpleCondition("count", "gt", 10)
        assert c.evaluate({"count": 15}) is True
        assert c.evaluate({"count": 5}) is False

    def test_simple_contains(self):
        c = SimpleCondition("name", "contains", "test")
        assert c.evaluate({"name": "my_test_func"}) is True
        assert c.evaluate({"name": "production"}) is False

    def test_simple_exists(self):
        c = SimpleCondition("key", "exists", None)
        assert c.evaluate({"key": "val"}) is True
        assert c.evaluate({}) is False

    def test_simple_matches(self):
        c = SimpleCondition("email", "matches", r".*@example\.com")
        assert c.evaluate({"email": "user@example.com"}) is True
        assert c.evaluate({"email": "user@other.com"}) is False

    def test_and_condition(self):
        c = AndCondition([
            SimpleCondition("a", "eq", 1),
            SimpleCondition("b", "eq", 2),
        ])
        assert c.evaluate({"a": 1, "b": 2}) is True
        assert c.evaluate({"a": 1, "b": 3}) is False

    def test_or_condition(self):
        c = OrCondition([
            SimpleCondition("a", "eq", 1),
            SimpleCondition("b", "eq", 2),
        ])
        assert c.evaluate({"a": 1, "b": 0}) is True
        assert c.evaluate({"a": 0, "b": 0}) is False

    def test_not_condition(self):
        c = NotCondition(SimpleCondition("x", "eq", 5))
        assert c.evaluate({"x": 3}) is True
        assert c.evaluate({"x": 5}) is False

    def test_condition_compiler(self):
        c = ConditionCompiler.compile({
            "type": "and",
            "conditions": [
                {"type": "simple", "field": "a", "op": "eq", "value": 1},
                {"type": "simple", "field": "b", "op": "gt", "value": 0},
            ],
        })
        assert isinstance(c, AndCondition)
        assert c.evaluate({"a": 1, "b": 5}) is True


# ── Actions ────────────────────────────────────────────────────

class TestActions:
    def test_notify_action(self):
        a = NotifyAction("n1", "Hello {name}")
        result = asyncio.run(
            a.execute({"name": "World"})
        )
        assert result.success is True
        assert result.output["message"] == "Hello World"

    def test_delay_action(self):
        a = DelayAction("d1", seconds=0.01)
        result = asyncio.run(a.execute({}))
        assert result.success is True

    def test_set_variable_action(self):
        ctx = {}
        a = SetVariableAction("sv1", "key", "value")
        result = asyncio.run(a.execute(ctx))
        assert result.success is True
        assert ctx["key"] == "value"

    def test_action_result(self):
        r = ActionResult(success=True, output="ok", duration_ms=10.5)
        d = r.to_dict()
        assert d["success"] is True
        assert d["output"] == "ok"

    def test_action_factory(self):
        a = ActionFactory.create({"type": "notify", "id": "af1", "message": "hi"})
        assert isinstance(a, NotifyAction)

    def test_parallel_action(self):
        a1 = NotifyAction("p1", "msg1")
        a2 = NotifyAction("p2", "msg2")
        pa = ParallelAction("par", [a1, a2])
        result = asyncio.run(pa.execute({}))
        assert result.success is True


# ── Validation ─────────────────────────────────────────────────

class TestValidation:
    def test_valid_workflow(self):
        result = validate_workflow({
            "id": "wf1",
            "name": "Test Workflow",
            "steps": [{"name": "Step 1", "action": "notify"}],
        })
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_id(self):
        result = validate_workflow({"name": "No ID"})
        assert result.valid is False
        assert any(e.field == "id" for e in result.errors)

    def test_missing_name(self):
        result = validate_workflow({"id": "wf1"})
        assert result.valid is False
        assert any(e.field == "name" for e in result.errors)

    def test_empty_steps_warning(self):
        result = validate_workflow({"id": "wf1", "name": "Test", "steps": []})
        assert any(e.severity == "warning" for e in result.errors)


# ── Storage ────────────────────────────────────────────────────

class TestStorage:
    def setup_method(self):
        import tempfile
        self.storage = WorkflowStorage(data_dir=tempfile.mkdtemp())

    def test_save_and_load(self):
        data = {"id": "wf1", "name": "Test"}
        assert self.storage.save_workflow(data) is True
        loaded = self.storage.load_workflow("wf1")
        assert loaded["id"] == "wf1"

    def test_list_workflows(self):
        self.storage.save_workflow({"id": "a", "name": "A"})
        self.storage.save_workflow({"id": "b", "name": "B"})
        ws = self.storage.list_workflows()
        assert len(ws) == 2

    def test_delete_workflow(self):
        self.storage.save_workflow({"id": "del", "name": "Del"})
        assert self.storage.delete_workflow("del") is True
        assert self.storage.load_workflow("del") is None

    def test_save_execution(self):
        assert self.storage.save_execution("wf1", "ex1", {"status": "ok"}) is True
        loaded = self.storage.load_execution("wf1", "ex1")
        assert loaded["status"] == "ok"


# ── WorkflowEngine ─────────────────────────────────────────────

class TestWorkflowEngine:
    def setup_method(self):
        import tempfile
        self.engine = WorkflowEngine(
            storage=WorkflowStorage(data_dir=tempfile.mkdtemp())
        )

    def test_load_from_config(self):
        wf = self.engine.load_from_config({
            "id": "test-wf",
            "name": "Test",
            "steps": [{"type": "notify", "id": "s1", "params": {"message": "hi"}}],
        })
        assert wf.id == "test-wf"
        assert len(wf.steps) == 1

    def test_list_workflows(self):
        self.engine.load_from_config({"id": "wf1", "name": "W1", "steps": []})
        self.engine.load_from_config({"id": "wf2", "name": "W2", "steps": []})
        assert len(self.engine.list_workflows()) == 2

    def test_get_workflow(self):
        self.engine.load_from_config({"id": "g1", "name": "G1", "steps": []})
        assert self.engine.get_workflow("g1") is not None
        assert self.engine.get_workflow("nonexistent") is None

    def test_delete_workflow(self):
        self.engine.load_from_config({"id": "d1", "name": "D1", "steps": []})
        assert self.engine.delete_workflow("d1") is True
        assert self.engine.get_workflow("d1") is None

    def test_execute_workflow(self):
        self.engine.load_from_config({
            "id": "exec1",
            "name": "Exec Test",
            "steps": [
                {"type": "set_variable", "id": "sv1", "params": {"key": "x", "value": 42}},
                {"type": "notify", "id": "n1", "params": {"message": "done"}},
            ],
        })
        result = asyncio.run(
            self.engine.execute("exec1", {"input": "test"})
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 2

    def test_execute_with_condition_met(self):
        self.engine.load_from_config({
            "id": "cond1",
            "name": "Conditional",
            "conditions": [{"type": "simple", "field": "run", "op": "eq", "value": True}],
            "steps": [{"type": "notify", "id": "n1", "params": {"message": "ran"}}],
        })
        result = asyncio.run(
            self.engine.execute("cond1", {"run": True})
        )
        assert result.status == ExecutionStatus.COMPLETED

    def test_execute_with_condition_not_met(self):
        self.engine.load_from_config({
            "id": "cond2",
            "name": "Conditional Skip",
            "conditions": [{"type": "simple", "field": "run", "op": "eq", "value": True}],
            "steps": [{"type": "notify", "id": "n1", "params": {"message": "ran"}}],
        })
        result = asyncio.run(
            self.engine.execute("cond2", {"run": False})
        )
        assert result.status == ExecutionStatus.SKIPPED

    def test_get_stats(self):
        stats = self.engine.get_stats()
        assert "registered_workflows" in stats
        assert "total_executions" in stats

    def test_singleton(self):
        e1 = get_workflow_engine()
        e2 = get_workflow_engine()
        assert e1 is e2
