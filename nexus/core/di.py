"""
NEXUS Dependency Injection Container.

Provides a simple DI container for managing service dependencies.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')


@dataclass
class DIContainer:
    """
    Simple DI container with factory registration.

    Usage:
        container = DIContainer()
        container.register(MyService, lambda: MyService())
        instance = container.resolve(MyService)
    """
    _factories: dict[type, Callable[..., Any]] = field(default_factory=dict)
    _singletons: dict[type, Any] = field(default_factory=dict)

    def register(self, interface: type[T], factory: Callable[..., T]) -> None:
        """Register a factory for an interface."""
        self._factories[interface] = factory

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """Register a singleton instance."""
        self._singletons[interface] = instance

    def resolve(self, interface: type[T]) -> T:
        """Resolve an interface to an instance."""
        if interface in self._singletons:
            return self._singletons[interface]
        if interface in self._factories:
            instance = self._factories[interface]()
            # Store as singleton by default
            self._singletons[interface] = instance
            return instance
        raise KeyError(f"No registration for {interface}")

    def clear(self) -> None:
        """Clear all registrations (useful for testing)."""
        self._factories.clear()
        self._singletons.clear()


# Global container
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container."""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def configure_container() -> None:
    """Configure all dependencies in the container."""
    from nexus.core.config import get_settings

    container = get_container()
    settings = get_settings()

    # Register services
    from nexus.memory.chroma_service import NexusMemoryService
    from nexus.knowledge.knowledge_graph import KnowledgeGraph
    from nexus.security.guardrails import Guardrails
    from nexus.security.audit import AuditLogger

    # Memory service
    container.register(
        NexusMemoryService,
        lambda: NexusMemoryService(persist_dir=settings.chroma_persist_dir)
    )

    # Knowledge graph
    container.register(KnowledgeGraph, KnowledgeGraph)

    # Security
    container.register(Guardrails, Guardrails)
    container.register(AuditLogger, AuditLogger)


def reset_container() -> None:
    """Reset the global container (for testing)."""
    global _container
    if _container:
        _container.clear()
    _container = None