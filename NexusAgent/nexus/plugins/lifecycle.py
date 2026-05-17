"""
NEXUS Plugin Lifecycle — Install, uninstall, update with rollback.

Handles the filesystem side of plugin management:
  - Install from directory, zip archive, or standalone manifest
  - Uninstall with cleanup
  - Update with automatic rollback on failure
  - High-level :class:`PluginLifecycleManager` for use by the engine
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from nexus.plugins.exceptions import (
    PluginError,
    PluginManifestError,
    PluginNotFoundError,
)
from nexus.plugins.loader import _find_manifest_file, _parse_manifest_file, discover_plugins, validate_manifest
from nexus.plugins.manifest import PluginManifest, PluginStatus
from nexus.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Low-level install / uninstall / update functions
# ═══════════════════════════════════════════════════════════════════


def _read_manifest_from_dir(directory: Path) -> dict[str, Any]:
    """Find and parse a plugin manifest file inside *directory*.

    Searches for ``plugin.json``, ``plugin.yaml``, or ``plugin.yml`` in order.

    Returns:
        Raw dictionary parsed from the manifest file.

    Raises:
        PluginManifestError: If no manifest file is found or it is invalid.
    """
    manifest_file = _find_manifest_file(directory)
    if manifest_file is None:
        raise PluginManifestError(
            plugin_id=None,
            reason=f"No plugin.json or plugin.yaml found in {directory}",
            details={"directory": str(directory)},
        )
    return _parse_manifest_file(manifest_file)


def install_plugin(source: str, target_dir: str) -> PluginManifest:
    """Install a plugin from *source* into *target_dir*.

    Supported source formats:

    - **Directory**: A directory containing ``plugin.json`` / ``plugin.yaml``.
    - **Zip archive** (``.zip``): Extracted into *target_dir*.
    - **Manifest file** (``.json`` / ``.yaml``): Copied as a manifest-only plugin.

    Args:
        source: Path to the plugin source (dir, zip, or manifest file).
        target_dir: Root directory under which plugin subdirectories live.

    Returns:
        The validated :class:`PluginManifest` of the newly installed plugin.

    Raises:
        PluginError: If the plugin already exists or the source is unsupported.
        PluginManifestError: If the manifest is invalid.
    """
    src = Path(source).resolve()
    dst = Path(target_dir).resolve()
    dst.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        manifest = _install_from_directory(src, dst)
    elif src.suffix.lower() == ".zip":
        manifest = _install_from_zip(src, dst)
    elif src.suffix.lower() in (".json", ".yaml", ".yml"):
        manifest = _install_from_manifest_file(src, dst)
    else:
        raise PluginError(
            message=f"Unsupported plugin source: {source}",
            details={
                "source": source,
                "supported_formats": "directory, .zip, .json, .yaml",
            },
        )

    logger.info("Installed plugin: %s v%s from %s", manifest.id, manifest.version, source)
    return manifest


def _install_from_directory(src: Path, dst: Path) -> PluginManifest:
    """Install a plugin by copying its directory."""
    manifest_data = _read_manifest_from_dir(src)
    manifest = validate_manifest(manifest_data)

    target = dst / manifest.id
    _ensure_not_installed(manifest.id, target)

    shutil.copytree(src, target, symlinks=False)
    logger.debug("Copied plugin directory %s → %s", src, target)
    return manifest


def _install_from_zip(src: Path, dst: Path) -> PluginManifest:
    """Install a plugin from a zip archive."""
    with tempfile.TemporaryDirectory(prefix="nexus_plugin_") as tmpdir:
        tmp_path = Path(tmpdir)
        with ZipFile(src, "r") as zf:
            zf.extractall(tmp_path)

        manifest_data = _read_manifest_from_dir(tmp_path)
        manifest = validate_manifest(manifest_data)

        target = dst / manifest.id
        _ensure_not_installed(manifest.id, target)

        shutil.copytree(tmp_path, target, symlinks=False)

    logger.debug("Extracted plugin zip %s → %s", src, target)
    return manifest


def _install_from_manifest_file(src: Path, dst: Path) -> PluginManifest:
    """Install a manifest-only plugin (no code, just a manifest file)."""
    if src.suffix.lower() in (".yaml", ".yml"):
        import yaml
        raw = src.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    else:
        raw = src.read_text(encoding="utf-8")
        data = json.loads(raw)

    manifest = validate_manifest(data)

    target = dst / manifest.id
    _ensure_not_installed(manifest.id, target)

    target.mkdir(parents=True, exist_ok=True)
    manifest_name = "plugin.json" if src.suffix.lower() == ".json" else "plugin.yaml"
    shutil.copy2(src, target / manifest_name)
    logger.debug("Copied manifest file %s → %s", src, target / manifest_name)
    return manifest


def _ensure_not_installed(plugin_id: str, target: Path) -> None:
    """Raise :class:`PluginError` if *target* already exists."""
    if target.exists():
        raise PluginError(
            message=f"Plugin '{plugin_id}' is already installed at {target}",
            plugin_id=plugin_id,
            details={"target": str(target)},
        )


def uninstall_plugin(plugin_id: str, target_dir: str) -> None:
    """Uninstall a plugin by removing its directory and registry entries.

    Args:
        plugin_id: The unique identifier of the plugin to remove.
        target_dir: Root plugin directory containing the plugin's subdirectory.

    Raises:
        PluginNotFoundError: If the plugin is not found on disk.
    """
    plugin_path = Path(target_dir).resolve() / plugin_id

    if not plugin_path.exists():
        raise PluginNotFoundError(plugin_id)

    # Remove from registry (silently ignore if not registered)
    registry = PluginRegistry()
    try:
        registry.unregister(plugin_id)
    except PluginNotFoundError:
        pass

    # Remove from disk
    shutil.rmtree(plugin_path)
    logger.info("Uninstalled plugin: %s (removed %s)", plugin_id, plugin_path)


# ═══════════════════════════════════════════════════════════════════
# Update with rollback
# ═══════════════════════════════════════════════════════════════════


def _backup_plugin(plugin_dir: Path) -> Path:
    """Create a timestamped backup of a plugin directory.

    Returns:
        Path to the backup directory.
    """
    backup_dir = plugin_dir.parent / f".bak_{plugin_dir.name}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(plugin_dir, backup_dir, symlinks=False)
    logger.debug("Backed up plugin: %s → %s", plugin_dir, backup_dir)
    return backup_dir


def _restore_from_backup(backup_path: Path, original_path: Path) -> None:
    """Restore a plugin directory from its backup and remove the backup."""
    if original_path.exists():
        shutil.rmtree(original_path)
    shutil.copytree(backup_path, original_path, symlinks=False)
    shutil.rmtree(backup_path)
    logger.info("Restored plugin from backup: %s", original_path)


def update_plugin(plugin_id: str, source: str, target_dir: str) -> PluginManifest:
    """Update a plugin with automatic rollback on failure.

    Steps:
      1. Backup the existing plugin directory.
      2. Remove the old plugin directory.
      3. Install the new version from *source*.
      4. If any step fails, restore from backup.

    Args:
        plugin_id: The plugin to update.
        source: Path to the new plugin source (dir, zip, or manifest).
        target_dir: Root plugin directory.

    Returns:
        The :class:`PluginManifest` of the updated plugin.

    Raises:
        PluginNotFoundError: If the plugin is not currently installed.
        PluginError: If the update fails and rollback is triggered (wraps the
            original error).
    """
    plugin_dir = Path(target_dir).resolve() / plugin_id
    if not plugin_dir.exists():
        raise PluginNotFoundError(plugin_id)

    # Phase 1: Backup
    backup_path = _backup_plugin(plugin_dir)

    # Phase 2: Remove old
    try:
        shutil.rmtree(plugin_dir)
    except OSError as exc:
        _restore_from_backup(backup_path, plugin_dir)
        raise PluginError(
            message=f"Failed to remove old plugin directory for '{plugin_id}': {exc}",
            plugin_id=plugin_id,
            details={"error": str(exc)},
        ) from exc

    # Phase 3: Install new
    try:
        manifest = install_plugin(source, target_dir)
    except Exception as exc:
        logger.error("Update install failed for '%s', rolling back...", plugin_id)
        _restore_from_backup(backup_path, plugin_dir)
        raise PluginError(
            message=f"Update of plugin '{plugin_id}' failed, rolled back: {exc}",
            plugin_id=plugin_id,
            details={"error": str(exc)},
        ) from exc

    # Phase 4: Update registry (preserve enabled/disabled status)
    registry = PluginRegistry()
    try:
        old_status = registry.get_status(plugin_id)
        registry.register(manifest, status=old_status)
        # Remove old instance reference so engine re-loads it
        if registry.get_instance(plugin_id) is not None:
            with registry._lock:
                registry._instances.pop(plugin_id, None)
    except PluginNotFoundError:
        registry.register(manifest, status=PluginStatus.INSTALLED)

    # Remove backup on success
    try:
        shutil.rmtree(backup_path)
    except OSError:
        pass

    logger.info("Updated plugin: %s → v%s", plugin_id, manifest.version)
    return manifest


# ═══════════════════════════════════════════════════════════════════
# High-level lifecycle manager
# ═══════════════════════════════════════════════════════════════════


class PluginLifecycleManager:
    """High-level interface for plugin lifecycle operations.

    Used by :class:`PluginEngine` to install, uninstall, update, enable,
    and disable plugins. All methods are async for consistency with the
    engine, although the underlying filesystem operations are synchronous.

    Usage::

        manager = PluginLifecycleManager(plugin_dir="./plugins")
        manifest = await manager.install("./my-plugin-v2.zip")
        await manager.enable("my-plugin")
    """

    def __init__(self, plugin_dir: str) -> None:
        self.plugin_dir = Path(plugin_dir).resolve()
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    async def install(self, source: str) -> PluginManifest:
        """Install a plugin from *source*.

        Wraps :func:`install_plugin` in an async context.
        """
        return await asyncio.to_thread(install_plugin, source, str(self.plugin_dir))

    async def uninstall(self, plugin_id: str) -> None:
        """Uninstall a plugin, shutting it down first if it is loaded."""
        registry = PluginRegistry()
        instance = registry.get_instance(plugin_id)
        if instance is not None:
            try:
                await instance.shutdown()
                logger.debug("Shut down plugin %s before uninstall", plugin_id)
            except Exception as exc:
                logger.error("Error shutting down plugin %s during uninstall: %s", plugin_id, exc)

        await asyncio.to_thread(uninstall_plugin, plugin_id, str(self.plugin_dir))

    async def update(self, plugin_id: str, source: str) -> PluginManifest:
        """Update a plugin from *source* with rollback protection."""
        return await asyncio.to_thread(update_plugin, plugin_id, source, str(self.plugin_dir))

    async def enable(self, plugin_id: str) -> None:
        """Set a plugin's status to ENABLED in the registry."""
        registry = PluginRegistry()
        registry.enable(plugin_id)

    async def disable(self, plugin_id: str) -> None:
        """Disable a plugin, shutting down its instance first."""
        registry = PluginRegistry()
        instance = registry.get_instance(plugin_id)
        if instance is not None:
            try:
                await instance.shutdown()
            except Exception as exc:
                logger.error("Error shutting down plugin %s during disable: %s", plugin_id, exc)
        registry.disable(plugin_id)
        # Remove instance so it gets re-initialized on next enable
        registry.set_data(plugin_id, "_disabled_at", __import__("time").time())

    async def list_discovered(self) -> list[PluginManifest]:
        """Scan the plugin directory for manifests (does not register)."""
        return await asyncio.to_thread(discover_plugins, str(self.plugin_dir))
