"""
NEXUS Plugin Registry — Thread-safe singleton registry of all plugins.

The registry is the single source of truth for:
  - Which plugins are installed (manifests)
  - Which plugins are loaded (instances)
  - Current status of every plugin
  - Arbitrary per-plugin runtime data
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from nexus.plugins.exceptions import PluginNotFoundError
from nexus.plugins.manifest import PluginBase, PluginManifest, PluginStatus

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Thread-safe singleton registry that tracks all plugin state.

    Usage::

        registry = PluginRegistry()
        registry.register(manifest)
        registry.enable("my-plugin")
        instance = registry.get_instance("my-plugin")
    """

    _instance: PluginRegistry | None = None
    _singleton_lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        with self._singleton_lock:
            if self._initialized:
                return
            self._plugins: dict[str, PluginManifest] = {}
            self._instances: dict[str, PluginBase] = {}
            self._statuses: dict[str, PluginStatus] = {}
            self._data: dict[str, dict[str, Any]] = {}
            self._lock: threading.Lock = threading.Lock()
            self._initialized = True

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        manifest: PluginManifest,
        status: PluginStatus = PluginStatus.INSTALLED,
    ) -> None:
        """Register a plugin manifest in the registry.

        If the plugin is already registered, this overwrites the previous
        manifest (useful during updates) but preserves the existing status
        unless one is explicitly provided.

        Args:
            manifest: The :class:`PluginManifest` to register.
            status: Initial status (default: :attr:`PluginStatus.INSTALLED`).
        """
        with self._lock:
            self._plugins[manifest.id] = manifest
            if manifest.id not in self._statuses:
                self._statuses[manifest.id] = status
            self._data.setdefault(manifest.id, {})
            logger.info("Registered plugin: %s v%s (%s)", manifest.id, manifest.version, status.value)

    def unregister(self, plugin_id: str) -> None:
        """Remove a plugin from the registry entirely.

        Args:
            plugin_id: The unique identifier of the plugin to remove.
        """
        with self._lock:
            self._plugins.pop(plugin_id, None)
            self._instances.pop(plugin_id, None)
            self._statuses.pop(plugin_id, None)
            self._data.pop(plugin_id, None)
            logger.info("Unregistered plugin: %s", plugin_id)

    # ── Lookup ──────────────────────────────────────────────────────

    def get(self, plugin_id: str) -> PluginManifest:
        """Get a plugin's manifest by ID.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            The :class:`PluginManifest`.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            manifest = self._plugins.get(plugin_id)
        if manifest is None:
            raise PluginNotFoundError(plugin_id)
        return manifest

    def get_instance(self, plugin_id: str) -> PluginBase | None:
        """Get the loaded instance of a plugin, or ``None`` if not loaded.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            The :class:`PluginBase` instance, or ``None``.
        """
        with self._lock:
            return self._instances.get(plugin_id)

    def set_instance(self, plugin_id: str, instance: PluginBase) -> None:
        """Store a loaded plugin instance.

        Args:
            plugin_id: Unique plugin identifier.
            instance: The :class:`PluginBase` instance.
        """
        with self._lock:
            self._instances[plugin_id] = instance

    def list_plugins(self) -> list[PluginManifest]:
        """Return all registered plugin manifests."""
        with self._lock:
            return list(self._plugins.values())

    def get_enabled(self) -> list[PluginManifest]:
        """Return manifests of all plugins whose status is ENABLED."""
        with self._lock:
            return [
                m for pid, m in self._plugins.items()
                if self._statuses.get(pid) == PluginStatus.ENABLED
            ]

    # ── Status Management ───────────────────────────────────────────

    def enable(self, plugin_id: str) -> None:
        """Set a plugin's status to ENABLED.

        Args:
            plugin_id: Unique plugin identifier.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            self._statuses[plugin_id] = PluginStatus.ENABLED
            logger.info("Enabled plugin: %s", plugin_id)

    def disable(self, plugin_id: str) -> None:
        """Set a plugin's status to DISABLED.

        Args:
            plugin_id: Unique plugin identifier.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            self._statuses[plugin_id] = PluginStatus.DISABLED
            logger.info("Disabled plugin: %s", plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        """Check whether a plugin is currently enabled.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            ``True`` if the plugin is ENABLED, ``False`` otherwise.
        """
        with self._lock:
            return self._statuses.get(plugin_id) == PluginStatus.ENABLED

    def get_status(self, plugin_id: str) -> PluginStatus:
        """Get the current status of a plugin.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            The :class:`PluginStatus`.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            status = self._statuses.get(plugin_id)
        if status is None:
            raise PluginNotFoundError(plugin_id)
        return status

    def set_status(self, plugin_id: str, status: PluginStatus) -> None:
        """Set the status of a plugin.

        Args:
            plugin_id: Unique plugin identifier.
            status: The new :class:`PluginStatus`.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            self._statuses[plugin_id] = status

    # ── Runtime Data ────────────────────────────────────────────────

    def get_data(self, plugin_id: str) -> dict[str, Any]:
        """Get the runtime data dict for a plugin.

        This is a mutable dict that plugins can use to store ephemeral
        state shared between the plugin and the engine.

        Args:
            plugin_id: Unique plugin identifier.

        Returns:
            A mutable dictionary of runtime data.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            return self._data.setdefault(plugin_id, {})

    def set_data(self, plugin_id: str, key: str, value: Any) -> None:
        """Set a single runtime data value for a plugin.

        Args:
            plugin_id: Unique plugin identifier.
            key: Data key.
            value: Any JSON-serializable value.

        Raises:
            PluginNotFoundError: If the plugin is not registered.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)
            self._data.setdefault(plugin_id, {})[key] = value

    # ── Introspection ───────────────────────────────────────────────

    def __len__(self) -> int:
        """Return the number of registered plugins."""
        with self._lock:
            return len(self._plugins)

    def __contains__(self, plugin_id: str) -> bool:
        """Check if a plugin is registered (``plugin_id in registry``)."""
        with self._lock:
            return plugin_id in self._plugins

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PluginRegistry(plugins={len(self._plugins)}, "
                f"instances={len(self._instances)}, "
                f"enabled={sum(1 for s in self._statuses.values() if s == PluginStatus.ENABLED)})"
            )
