"""Tests for the Plugin System."""

import pytest
import tempfile
from nexus.plugins.manifest import (
    PluginManifest, PluginBase, PluginScope, PluginPermission, PluginStatus,
)
from nexus.plugins.registry import PluginRegistry
from nexus.plugins.engine import PluginEngine
from nexus.plugins.sandbox import PluginSandbox, TokenBucket
from nexus.plugins.exceptions import (
    PluginError, PluginNotFoundError, PluginPermissionDenied, PluginRateLimitError,
)


class TestPluginManifest:
    def test_create_manifest(self):
        m = PluginManifest(id="test-plugin", name="Test Plugin", version="1.0.0", description="A test plugin")
        assert m.id == "test-plugin"
        assert m.name == "Test Plugin"

    def test_manifest_defaults(self):
        m = PluginManifest(id="p1", name="P1", version="0.1.0")
        assert m.hooks == []
        assert m.tools == []
        assert m.mcps == []
        assert m.permissions == []

    def test_manifest_with_hooks(self):
        m = PluginManifest(id="p2", name="P2", version="1.0.0", hooks=["before_tool", "after_tool"])
        assert "before_tool" in m.hooks

    def test_manifest_with_permissions(self):
        m = PluginManifest(id="p3", name="P3", version="1.0.0", permissions=[PluginPermission.NETWORK, PluginPermission.FILESYSTEM_READ])
        assert PluginPermission.NETWORK in m.permissions


class TestPluginRegistry:
    def setup_method(self):
        self.registry = PluginRegistry()

    def test_register_and_get(self):
        m = PluginManifest(id="r1", name="R1", version="1.0.0")
        self.registry.register(m)
        assert self.registry.get("r1") is not None
        assert self.registry.get("r1").id == "r1"

    def test_get_nonexistent_raises(self):
        with pytest.raises(PluginNotFoundError):
            self.registry.get("nonexistent")

    def test_unregister(self):
        m = PluginManifest(id="r2", name="R2", version="1.0.0")
        self.registry.register(m)
        self.registry.unregister("r2")
        with pytest.raises(PluginNotFoundError):
            self.registry.get("r2")

    def test_enable_disable(self):
        m = PluginManifest(id="r3", name="R3", version="1.0.0")
        self.registry.register(m)
        self.registry.enable("r3")
        assert self.registry.is_enabled("r3") is True
        self.registry.disable("r3")
        assert self.registry.is_enabled("r3") is False

    def test_get_status(self):
        m = PluginManifest(id="r4", name="R4", version="1.0.0")
        self.registry.register(m)
        self.registry.set_status("r4", PluginStatus.ENABLED)
        assert self.registry.get_status("r4") == PluginStatus.ENABLED

    def test_list_plugins(self):
        m = PluginManifest(id="r5", name="R5", version="1.0.0")
        self.registry.register(m)
        plugins = self.registry.list_plugins()
        assert isinstance(plugins, (dict, list))


class TestPluginSandbox:
    def setup_method(self):
        self.sandbox = PluginSandbox()

    def test_check_permission_granted(self):
        m = PluginManifest(id="s1", name="S1", version="1.0.0", permissions=[PluginPermission.NETWORK])
        assert self.sandbox.check_permission(m, PluginPermission.NETWORK) is True

    def test_check_permission_denied(self):
        m = PluginManifest(id="s2", name="S2", version="1.0.0", permissions=[])
        with pytest.raises(PluginPermissionDenied):
            self.sandbox.check_permission(m, PluginPermission.SHELL)

    def test_validate_path(self):
        result = self.sandbox.validate_path("/tmp/test.txt", allowed_bases=["/tmp"])
        assert isinstance(result, bool)


class TestTokenBucket:
    def test_consume_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.consume(6) is False

    def test_refill(self):
        import time
        bucket = TokenBucket(capacity=10, refill_rate=100.0)
        bucket.consume(10)
        time.sleep(0.05)
        assert bucket.consume(1) is True


class TestPluginEngine:
    def setup_method(self):
        self.engine = PluginEngine(plugin_dir=tempfile.mkdtemp())

    def test_get_status_summary(self):
        summary = self.engine.get_status_summary()
        assert "total" in summary
        assert "plugins" in summary

    def test_get_hooks(self):
        # get_hooks takes a plugin_id, not a hook name
        # With no plugins installed, should raise or return empty
        try:
            hooks = self.engine.get_hooks("nonexistent")
            assert isinstance(hooks, list)
        except PluginNotFoundError:
            pass  # expected when plugin doesn't exist

    def test_get_tools(self):
        try:
            tools = self.engine.get_tools("nonexistent")
            assert isinstance(tools, list)
        except PluginNotFoundError:
            pass  # expected when plugin doesn't exist


class TestExceptions:
    def test_plugin_error(self):
        with pytest.raises(PluginError):
            raise PluginError("test error")

    def test_plugin_not_found(self):
        with pytest.raises(PluginNotFoundError):
            raise PluginNotFoundError("missing")

    def test_permission_denied(self):
        with pytest.raises(PluginPermissionDenied):
            raise PluginPermissionDenied("plugin-id", "network")

    def test_rate_limit(self):
        with pytest.raises(PluginRateLimitError):
            raise PluginRateLimitError("too fast")
