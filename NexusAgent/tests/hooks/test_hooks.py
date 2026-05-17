"""Tests for the Hooks System."""

import pytest
import asyncio
from nexus.hooks import (
    HookEngine, HookPoint, HookResult, HookAction, HookContext,
    get_dispatcher, register_hook, dispatch_hook,
)
from nexus.hooks.dispatcher import HookDispatcher


class TestHookPoint:
    def test_all_points_exist(self):
        assert HookPoint.BEFORE_PROMPT.value == "before_prompt"
        assert HookPoint.BEFORE_TOOL.value == "before_tool"
        assert HookPoint.AFTER_TOOL.value == "after_tool"
        assert HookPoint.ON_ERROR.value == "on_error"
        assert HookPoint.BEFORE_AGENT_SPAWN.value == "before_agent_spawn"

    def test_point_count(self):
        assert len(HookPoint) >= 18


class TestHookContext:
    def test_create_context(self):
        ctx = HookContext(hook_point=HookPoint.BEFORE_TOOL, data={"tool_name": "read_file"})
        assert ctx.hook_point == HookPoint.BEFORE_TOOL
        assert ctx.data["tool_name"] == "read_file"

    def test_context_with_plugin_id(self):
        ctx = HookContext(hook_point=HookPoint.BEFORE_TOOL, plugin_id="my-plugin", data={"key": "val"})
        assert ctx.plugin_id == "my-plugin"


class TestHookResult:
    def test_allow_result(self):
        r = HookResult(action=HookAction.ALLOW)
        assert r.action == HookAction.ALLOW

    def test_block_result(self):
        r = HookResult(action=HookAction.BLOCK, message="not allowed", blocking=True)
        assert r.action == HookAction.BLOCK
        assert r.message == "not allowed"
        assert r.blocking is True

    def test_modify_result(self):
        r = HookResult(action=HookAction.MODIFY, modified_data={"key": "new"})
        assert r.action == HookAction.MODIFY
        assert r.modified_data["key"] == "new"


class TestHookDispatcher:
    def setup_method(self):
        self.dispatcher = HookDispatcher()

    def test_register_and_dispatch(self):
        called = []

        async def handler(ctx):
            called.append(True)
            return HookResult(action=HookAction.ALLOW)

        self.dispatcher.register(HookPoint.BEFORE_TOOL, handler, plugin_id="test", priority=50)
        results = asyncio.run(
            self.dispatcher.dispatch(HookPoint.BEFORE_TOOL, HookContext(hook_point=HookPoint.BEFORE_TOOL, data={}))
        )
        assert len(called) == 1
        assert len(results) == 1
        assert results[0].action == HookAction.ALLOW

    def test_block_short_circuits(self):
        calls = []

        async def blocker(ctx):
            calls.append("blocker")
            return HookResult(action=HookAction.BLOCK, blocking=True)

        async def after(ctx):
            calls.append("after")
            return HookResult(action=HookAction.ALLOW)

        self.dispatcher.register(HookPoint.BEFORE_TOOL, blocker, plugin_id="blocker", priority=10)
        self.dispatcher.register(HookPoint.BEFORE_TOOL, after, plugin_id="after", priority=20)

        asyncio.run(
            self.dispatcher.dispatch(HookPoint.BEFORE_TOOL, HookContext(hook_point=HookPoint.BEFORE_TOOL, data={}), blocking=True)
        )
        assert calls == ["blocker"]

    def test_unregister(self):
        async def handler(ctx):
            return HookResult(action=HookAction.ALLOW)

        self.dispatcher.register(HookPoint.BEFORE_TOOL, handler, plugin_id="test-p")
        count = self.dispatcher.unregister(HookPoint.BEFORE_TOOL, "test-p")
        assert count >= 1

    def test_get_status(self):
        status = self.dispatcher.get_status()
        assert isinstance(status, dict)


class TestHookEngine:
    def setup_method(self):
        self.engine = HookEngine()

    def test_get_status(self):
        status = self.engine.get_status()
        assert isinstance(status, dict)

    def test_register_custom_handler(self):
        async def my_hook(ctx):
            return HookResult(action=HookAction.LOG)

        self.engine.register_handler(HookPoint.ON_ERROR, my_hook, plugin_id="custom", priority=100)
        status = self.engine.get_status()
        assert isinstance(status, dict)


class TestBuiltinHooks:
    def test_audit_hook_import(self):
        from nexus.hooks.builtins.audit_hook import create_audit_hook_handlers
        handlers = create_audit_hook_handlers()
        assert len(handlers) > 0

    def test_permission_hook_import(self):
        from nexus.hooks.builtins.permission_hook import create_permission_hook_handlers
        handlers = create_permission_hook_handlers()
        assert len(handlers) > 0

    def test_logging_hook_import(self):
        from nexus.hooks.builtins import logging_hook
        assert logging_hook is not None
