"""
NEXUS Plugin System — Modular plugin architecture for extending NEXUS.

The plugin system allows third-party developers to extend NEXUS with
custom tools, hooks, MCPs, and UI components. Every plugin is defined
by a :class:`PluginManifest` and implements the :class:`PluginBase`
abstract interface.

Architecture::

    PluginEngine (orchestrator)
       ├── PluginRegistry (thread-safe singleton — tracks all plugins)
       ├── PluginSandbox (security — permissions, rate limits, audit)
       ├── PluginLifecycleManager (install / update / uninstall + rollback)
       ├── loader (discovery + dynamic import)
       └── PluginBase instances (the actual plugin code)

Quick start::

    from nexus.plugins import PluginEngine

    engine = PluginEngine(plugin_dir="./plugins")
    await engine.initialize()
    # All plugins are now loaded and running
    ...
    await engine.shutdown()
"""

from __future__ import annotations

from nexus.plugins.engine import PluginEngine
from nexus.plugins.manifest import PluginBase, PluginManifest, PluginPermission, PluginScope, PluginStatus
from nexus.plugins.lifecycle import install_plugin, uninstall_plugin

__all__ = [
    "PluginEngine",
    "PluginBase",
    "PluginManifest",
    "PluginStatus",
    "PluginScope",
    "PluginPermission",
    "install_plugin",
    "uninstall_plugin",
]
