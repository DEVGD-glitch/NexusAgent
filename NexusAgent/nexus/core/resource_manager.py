"""
NEXUS Resource Manager — Memory and CPU optimization.

Features:
  - LRU cache with TTL for frequently accessed data
  - Automatic cleanup of stale resources
  - Memory usage monitoring
  - Lazy loading support
"""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """An entry in the LRU cache."""
    value: Any
    created_at: float
    ttl: float  # Time-to-live in seconds
    access_count: int = 0


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.

    Automatically evicts entries when they exceed TTL or when
    the cache size exceeds max_size.
    """

    def __init__(self, max_size: int = 100, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None if not found or expired."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry.created_at > entry.ttl:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            entry.access_count += 1
            self._cache.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl,
            )

    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        async with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if now - v.created_at > v.ttl
            ]
            for key in expired_keys:
                del self._cache[key]
        return len(expired_keys)

    @property
    def size(self) -> int:
        return len(self._cache)


class ResourceManager:
    """
    Manages NEXUS resources: memory, cache, and cleanup.

    Features:
      - LRU cache for frequently accessed data
      - Periodic cleanup of stale resources
      - Memory usage monitoring
      - Lazy module loading
    """

    def __init__(self, cache_max_size: int = 100, cache_ttl: float = 300.0):
        self.cache = LRUCache(max_size=cache_max_size, default_ttl=cache_ttl)
        self._loaded_modules: dict[str, Any] = {}
        self._start_time = time.time()

    def lazy_import(self, module_path: str) -> Any:
        """
        Lazily import a module. Only imports on first access.

        Args:
            module_path: Dotted module path (e.g., 'nexus.memory.chroma_service')

        Returns:
            The imported module.
        """
        if module_path not in self._loaded_modules:
            try:
                import importlib
                self._loaded_modules[module_path] = importlib.import_module(module_path)
                logger.debug("Lazy-loaded module: %s", module_path)
            except ImportError as exc:
                logger.warning("Failed to lazy-load %s: %s", module_path, exc)
                raise
        return self._loaded_modules[module_path]

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage information."""
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            return {
                "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
                "vms_mb": round(mem_info.vms / 1024 / 1024, 1),
                "cache_entries": self.cache.size,
                "loaded_modules": len(self._loaded_modules),
                "uptime_seconds": round(time.time() - self._start_time),
            }
        except ImportError:
            # psutil not available, provide basic info
            return {
                "rss_mb": "N/A (psutil not installed)",
                "cache_entries": self.cache.size,
                "loaded_modules": len(self._loaded_modules),
                "uptime_seconds": round(time.time() - self._start_time),
            }

    async def periodic_cleanup(self) -> None:
        """Run periodic cleanup tasks."""
        removed = await self.cache.cleanup_expired()
        if removed > 0:
            logger.debug("Cleaned up %d expired cache entries", removed)


# Global resource manager instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager singleton."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
