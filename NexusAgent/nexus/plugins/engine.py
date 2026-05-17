"""
NEXUS Plugin Engine — Central orchestrator for the plugin system.

The :class:`PluginEngine` is the main entry point. It:
  - Discovers plugins from the plugin directory
  - Loads and initialises plugins
  - Manages the full lifecycle (start, stop, reload)
  - Exposes plugin capabilities (hooks, tools, MCPs) to the rest of NEXUS

Usage::

    engine = PluginEngine(plugin_dir="./nexus_data/plugins")
    await engine.initialize()
    ...
    await engine.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

from nexus.plugins.exceptions import PluginError, PluginLoadError, PluginNotFoundError
from nexus.plugins.lifecycle import PluginLifecycleManager
from nexus.plugins.loader import discover_plugins, load_plugin
from nexus.plugins.manifest import PluginBase, PluginManifest, PluginStatus
from nexus.plugins.registry import PluginRegistry
from nexus.plugins.sandbox import PluginSandbox

logger = logging.getLogger(__name__)


class PluginEngine:
    """Central engine that manages the full lifecycle of all plugins.

    Thread-safe: all mutable state is guarded by a re-entrant lock.
    Async-safe: initialise and shutdown can be awaited.
    """

    def __init__(self, plugin_dir: str) -> None:
        self.plugin_dir = Path(plugin_dir).resolve()
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

        self._registry = PluginRegistry()
        self._sandbox = PluginSandbox()
        self._lifecycle = PluginLifecycleManager(str(self.plugin_dir))
        self._lock = threading.RLock()
        self._initialized = False
        self._shutting_down = False

    # ── Properties ──────────────────────────────────────────────────

    @property
    def registry(self) -> PluginRegistry:
        """The shared :class:`PluginRegistry` singleton."""
        return self._registry

    @property
    def sandbox(self) -> PluginSandbox:
        """The shared :class:`PluginSandbox` instance."""
        return self._sandbox

    @property
    def lifecycle(self) -> PluginLifecycleManager:
        """The shared :class:`PluginLifecycleManager` instance."""
        return self._lifecycle

    # ── Initialization & Shutdown ───────────────────────────────────

    async def initialize(self) -> None:
        """Discover, load, and initialize all plugins in the plugin directory.

        This is idempotent — calling it twice is a no-op on the second call.
        Each plugin is loaded sequentially so errors in one do not block others.
        """
        with self._lock:
            if self._initialized:
                logger.warning("PluginEngine already initialized, skipping")
                return
            self._initialized = True

        logger.info("Initializing PluginEngine from: %s", self.plugin_dir)

        # Phase 1: Discover manifests
        manifests = discover_plugins(str(self.plugin_dir))
        if not manifests:
            logger.info("No plugins found in %s", self.plugin_dir)
            return

        # Phase 2: Register all manifests first (so they are visible)
        for manifest in manifests:
            self._registry.register(manifest, status=PluginStatus.DISABLED)

        # Phase 3: Load and initialize each plugin
        loaded_count = 0
        for manifest in manifests:
            instance = await self._load_and_initialize(manifest)
            if instance is not None:
                loaded_count += 1

        enabled_count = len(self._registry.get_enabled())
        logger.info(
            "PluginEngine initialized: %d discovered, %d loaded+enabled, %d total enabled",
            len(manifests),
            loaded_count,
            enabled_count,
        )

    async def _load_and_initialize(self, manifest: PluginManifest) -> PluginBase | None:
        """Load a single plugin, initialize it, and mark it as enabled.

        Returns the plugin instance on success or ``None`` if loading failed
        (the plugin is marked as ERROR in the registry).
        """
        plugin_dir = str(self.plugin_dir / manifest.id)

        try:
            instance = load_plugin(manifest, plugin_dir=plugin_dir)
        except PluginLoadError as exc:
            self._registry.set_status(manifest.id, PluginStatus.ERROR)
            self._sandbox.log_action(
                manifest, "load", result="error",
                details={"error": exc.message},
            )
            logger.error("Failed to load plugin %s: %s", manifest.id, exc)
            return None
        except Exception as exc:
            self._registry.set_status(manifest.id, PluginStatus.ERROR)
            self._sandbox.log_action(
                manifest, "load", result="error",
                details={"error": str(exc)},
            )
            logger.exception("Unexpected error loading plugin %s: %s", manifest.id, exc)
            return None

        # Store instance
        self._registry.set_instance(manifest.id, instance)

        # Call initialize
        try:
            await instance.initialize()
        except Exception as exc:
            self._registry.set_status(manifest.id, PluginStatus.ERROR)
            self._sandbox.log_action(
                manifest, "initialize", result="error",
                details={"error": str(exc)},
            )
            logger.exception("Plugin %s failed to initialize: %s", manifest.id, exc)
            return None

        # Mark as enabled
        self._registry.enable(manifest.id)
        self._sandbox.log_action(manifest, "initialize", result="success")
        logger.info("Plugin loaded and enabled: %s v%s", manifest.id, manifest.version)
        return instance

    async def shutdown(self) -> None:
        """Shut down the engine and all loaded plugins gracefully.

        Plugins are shut down in reverse-registration order. If a plugin's
        :meth:`PluginBase.shutdown` raises, the error is logged but does
        **not** prevent other plugins from shutting down.
        """
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True

        logger.info("Shutting down PluginEngine...")

        manifests = self._registry.list_plugins()
        # Shut down in reverse order so dependencies are released last
        for manifest in reversed(manifests):
            if not self._registry.is_enabled(manifest.id):
                continue
            instance = self._registry.get_instance(manifest.id)
            if instance is None:
                continue
            try:
                await instance.shutdown()
                self._sandbox.log_action(manifest, "shutdown", result="success")
                logger.debug("Plugin shutdown: %s", manifest.id)
            except Exception as exc:
                self._sandbox.log_action(
                    manifest, "shutdown", result="error",
                    details={"error": str(exc)},
                )
                logger.error("Error shutting down plugin %s: %s", manifest.id, exc)

        logger.info("PluginEngine shutdown complete")

    # ── Reload ──────────────────────────────────────────────────────

    async def reload_plugin(self, plugin_id: str) -> PluginBase | None:
        """Reload a single plugin: shutdown, re-import, re-initialize.

        Args:
            plugin_id: The unique identifier of the plugin to reload.

        Returns:
            The new plugin instance, or ``None`` if reloading failed.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        manifest = self._registry.get(plugin_id)  # raises if not found

        # Shutdown existing instance
        instance = self._registry.get_instance(plugin_id)
        if instance is not None:
            try:
                await instance.shutdown()
                logger.debug("Plugin %s shut down for reload", plugin_id)
            except Exception as exc:
                logger.error("Error shutting down plugin %s during reload: %s", plugin_id, exc)

        # Clear instance and set to DISABLED
        self._registry.disable(plugin_id)
        with self._registry._lock:
            self._registry._instances.pop(plugin_id, None)

        # Reload (re-discover manifest from disk in case it changed)
        discovered = discover_plugins(str(self.plugin_dir))
        for d_manifest in discovered:
            if d_manifest.id == plugin_id:
                manifest = d_manifest
                self._registry.register(manifest, status=PluginStatus.DISABLED)
                break

        return await self._load_and_initialize(manifest)

    async def reload_all(self) -> dict[str, bool]:
        """Reload every registered plugin.

        Returns:
            A dict mapping ``plugin_id`` to a boolean indicating reload success.
        """
        manifests = self._registry.list_plugins()
        results: dict[str, bool] = {}
        for manifest in manifests:
            try:
                result = await self.reload_plugin(manifest.id)
                results[manifest.id] = result is not None
            except Exception as exc:
                logger.error("Failed to reload plugin %s: %s", manifest.id, exc)
                results[manifest.id] = False
        return results

    # ── Capability Queries ──────────────────────────────────────────

    def get_hooks(self, plugin_id: str) -> list[str]:
        """Get all hook identifiers registered by a plugin.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            List of hook name strings.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        manifest = self._registry.get(plugin_id)
        return list(manifest.hooks)

    def get_tools(self, plugin_id: str) -> list[str]:
        """Get all tool names provided by a plugin.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            List of tool name strings.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        manifest = self._registry.get(plugin_id)
        return list(manifest.tools)

    def get_mcps(self, plugin_id: str) -> list[str]:
        """Get all MCP (Model Context Protocol) names provided by a plugin.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            List of MCP name strings.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        manifest = self._registry.get(plugin_id)
        return list(manifest.mcps)

    def get_plugins_by_hook(self, hook: str) -> list[PluginManifest]:
        """Find all enabled plugins that register a specific hook.

        Args:
            hook: Hook name to search for (e.g. ``on_message``).

        Returns:
            List of :class:`PluginManifest` for matching enabled plugins.
        """
        return [
            m for m in self._registry.get_enabled()
            if hook in m.hooks
        ]

    def get_plugins_by_tool(self, tool: str) -> list[PluginManifest]:
        """Find all enabled plugins that provide a specific tool.

        Args:
            tool: Tool name to search for.

        Returns:
            List of :class:`PluginManifest` for matching enabled plugins.
        """
        return [
            m for m in self._registry.get_enabled()
            if tool in m.tools
        ]

    def get_plugins_by_permission(
        self,
        permission: "PluginPermission",
    ) -> list[PluginManifest]:
        """Find all enabled plugins that have a specific permission.

        Args:
            permission: The :class:`PluginPermission` to check.

        Returns:
            List of :class:`PluginManifest` for matching enabled plugins.
        """
        from nexus.plugins.manifest import PluginPermission

        return [
            m for m in self._registry.get_enabled()
            if permission in m.permissions or PluginPermission.ADMIN in m.permissions
        ]

    # ─── Introspection ──────────────────────────────────────────────

    def get_status_summary(self) -> dict[str, Any]:
        """Return a high-level summary of all plugin states.

        Useful for API endpoints and health checks.
        """
        manifests = self._registry.list_plugins()
        summary = {
            "total": len(manifests),
            "enabled": len(self._registry.get_enabled()),
            "plugins": [],
        }
        for m in manifests:
            instance = self._registry.get_instance(m.id)
            summary["plugins"].append({
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "status": self._registry.get_status(m.id).value,
                "loaded": instance is not None,
                "tools": len(m.tools),
                "hooks": len(m.hooks),
                "mcps": len(m.mcps),
                "permissions": [p.value for p in m.permissions],
            })
        return summary

    def is_loaded(self, plugin_id: str) -> bool:
        """Check if a plugin has been instantiated (loaded into memory)."""
        return self._registry.get_instance(plugin_id) is not None

    def __repr__(self) -> str:
        return (
            f"PluginEngine(dir={self.plugin_dir}, "
            f"plugins={len(self._registry)}, "
            f"enabled={len(self._registry.get_enabled())})"
        )
