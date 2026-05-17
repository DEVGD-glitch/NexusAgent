"""
NEXUS Plugin Loader — Discovery, validation, and dynamic import of plugins.

Responsibilities:
  - Scan a directory tree for ``plugin.json`` / ``plugin.yaml`` manifests
  - Validate raw manifest data against the :class:`PluginManifest` schema
  - Dynamically import a plugin's entry point and return a :class:`PluginBase` instance
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

from nexus.plugins.exceptions import PluginLoadError, PluginManifestError
from nexus.plugins.manifest import PluginBase, PluginManifest

logger = logging.getLogger(__name__)


# ── Manifest Parsing ────────────────────────────────────────────


def _parse_manifest_file(filepath: Path) -> dict[str, Any]:
    """Read and parse a plugin manifest file (JSON or YAML)."""
    suffix = filepath.suffix.lower()
    raw = filepath.read_text(encoding="utf-8")

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise PluginManifestError(
                plugin_id=None,
                reason=f"Cannot parse {filepath.name}: PyYAML is required. Install with ``pip install pyyaml``.",
                details={"file": str(filepath)},
            )
        try:
            data: Any = yaml.safe_load(raw)
        except Exception as exc:
            raise PluginManifestError(
                plugin_id=None,
                reason=f"Invalid YAML in {filepath.name}: {exc}",
                details={"file": str(filepath)},
            ) from exc
    elif suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PluginManifestError(
                plugin_id=None,
                reason=f"Invalid JSON in {filepath.name}: {exc}",
                details={"file": str(filepath), "position": exc.pos},
            ) from exc
    else:
        raise PluginManifestError(
            plugin_id=None,
            reason=f"Unsupported manifest format: {suffix}",
            details={"file": str(filepath)},
        )

    if not isinstance(data, dict):
        raise PluginManifestError(
            plugin_id=None,
            reason=f"Manifest {filepath.name} must be a JSON object, got {type(data).__name__}",
            details={"file": str(filepath)},
        )
    return data


def _find_manifest_file(directory: Path) -> Path | None:
    """Look for a plugin manifest file in a directory."""
    for candidate in ("plugin.json", "plugin.yaml", "plugin.yml"):
        candidate_path = directory / candidate
        if candidate_path.is_file():
            return candidate_path
    return None


# ── Public API ──────────────────────────────────────────────────


def validate_manifest(data: dict[str, Any]) -> PluginManifest:
    """Validate raw manifest data and return a :class:`PluginManifest`.

    Args:
        data: Dictionary of manifest fields (parsed from JSON or YAML).

    Returns:
        A validated :class:`PluginManifest` instance.

    Raises:
        PluginManifestError: If the data fails schema validation.
    """
    try:
        return PluginManifest.model_validate(data)
    except Exception as exc:
        plugin_id = data.get("id", "<unknown>")
        raise PluginManifestError(
            plugin_id=plugin_id,
            reason=str(exc),
            details={"raw_fields": list(data.keys())},
        ) from exc


def discover_plugins(path: str) -> list[PluginManifest]:
    """Scan a directory for plugin manifests and return validated manifests.

    Recursively searches *immediate* subdirectories of *path* for plugins.
    Each subdirectory should contain ``plugin.json`` or ``plugin.yaml``.

    Args:
        path: Root directory to scan for plugins.

    Returns:
        List of validated :class:`PluginManifest` objects.
    """
    base = Path(path).resolve()
    if not base.is_dir():
        logger.warning("Plugin directory does not exist: %s", base)
        return []

    manifests: list[PluginManifest] = []

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue

        # Ignore hidden directories and backup directories
        if entry.name.startswith(".") or entry.name.startswith("_backup"):
            continue

        manifest_file = _find_manifest_file(entry)
        if manifest_file is None:
            continue

        try:
            data = _parse_manifest_file(manifest_file)
            manifest = validate_manifest(data)
            manifests.append(manifest)
            logger.info("Discovered plugin: %s v%s at %s", manifest.id, manifest.version, entry.name)
        except PluginManifestError as exc:
            logger.error("Skipping %s: %s", entry.name, exc.message)
        except Exception as exc:
            logger.exception("Unexpected error discovering plugin in %s: %s", entry.name, exc)

    return manifests


def load_plugin(manifest: PluginManifest, plugin_dir: str = "") -> PluginBase:
    """Dynamically import a plugin from its manifest and return an instance.

    The *entry_point* field in the manifest must be in ``module:ClassName``
    format (e.g. ``web_search.plugin:WebSearchPlugin``). If *plugin_dir* is
    provided, it is temporarily added to ``sys.path`` so the import resolves.

    Args:
        manifest: The :class:`PluginManifest` with the entry point.
        plugin_dir: Absolute path to the plugin's directory (added to ``sys.path``).

    Returns:
        An instantiated :class:`PluginBase` subclass with ``.manifest`` set.

    Raises:
        PluginLoadError: If the entry point cannot be imported or instantiated.
    """
    if not manifest.entry_point:
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason="No entry_point specified in manifest. Set e.g. ``main:MyPlugin``.",
        )

    # Parse entry_point format: "package.module:ClassName"
    module_path, _, class_name = manifest.entry_point.partition(":")
    if not class_name:
        class_name = "Plugin"  # sensible default
    if not module_path:
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"Invalid entry_point format: {manifest.entry_point!r}. "
            f"Expected ``module:ClassName`` (e.g. ``main:MyPlugin``).",
        )

    # Add the plugin directory to sys.path so imports resolve
    if plugin_dir:
        resolved_dir = str(Path(plugin_dir).resolve())
        if resolved_dir not in sys.path:
            sys.path.insert(0, resolved_dir)
            logger.debug("Added %s to sys.path for plugin %s", resolved_dir, manifest.id)

    # Dynamically import the module
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"Cannot import module '{module_path}': {exc}",
        ) from exc

    # Locate the plugin class
    plugin_cls = getattr(module, class_name, None)
    if plugin_cls is None:
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"Class '{class_name}' not found in module '{module_path}'",
        )

    if not isinstance(plugin_cls, type):
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"'{class_name}' is not a class (got {type(plugin_cls).__name__})",
        )

    if not issubclass(plugin_cls, PluginBase):
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"'{class_name}' must be a subclass of PluginBase, "
            f"got bases: {[b.__name__ for b in plugin_cls.__bases__]}",
        )

    # Instantiate
    try:
        instance = plugin_cls()
    except Exception as exc:
        raise PluginLoadError(
            plugin_id=manifest.id,
            reason=f"Failed to instantiate plugin class '{class_name}': {exc}",
        ) from exc

    # Inject the manifest
    instance.manifest = manifest
    logger.debug("Loaded plugin instance: %s v%s", manifest.id, manifest.version)
    return instance
