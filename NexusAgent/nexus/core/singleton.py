"""
Thread-safe singleton pattern for NexusAgent core singletons.

Provides a reusable double-checked locking decorator to ensure
singleton instances are created exactly once, even under concurrent
access from multiple threads.

Usage:
    from nexus.core.singleton import thread_safe_singleton

    @thread_safe_singleton
    def get_my_service() -> MyService:
        return MyService()
"""

from __future__ import annotations

import threading
from typing import TypeVar, Type, Optional, Callable

T = TypeVar('T')


def thread_safe_singleton(factory: Callable[[], T]) -> Callable[[], T]:
    """Thread-safe singleton decorator using double-checked locking.

    Wraps a factory function so that:
    - The first call creates the instance under a lock.
    - Subsequent calls return the cached instance without acquiring the lock.

    Args:
        factory: A callable that returns a new instance of the singleton.

    Returns:
        A wrapper function that always returns the same instance.
    """
    instance: Optional[T] = None
    lock = threading.Lock()

    def get_instance() -> T:
        nonlocal instance
        if instance is None:
            with lock:
                if instance is None:
                    instance = factory()
        return instance

    return get_instance
