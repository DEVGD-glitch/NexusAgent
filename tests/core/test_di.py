"""
Tests for nexus.core.di - Dependency Injection Container.
"""

import pytest
from nexus.core.di import DIContainer, get_container


class DummyService:
    """Dummy service for testing."""
    def __init__(self, value="default"):
        self.value = value


class TestDIContainer:
    """Test cases for DIContainer."""

    @pytest.fixture
    def container(self):
        return DIContainer()

    def test_register_factory(self, container):
        """Register a factory."""
        container.register(DummyService, lambda: DummyService("test"))
        assert DummyService in container._factories

    def test_register_singleton(self, container):
        """Register a singleton."""
        service = DummyService("singleton")
        container.register_singleton(DummyService, service)
        assert DummyService in container._singletons

    def test_resolve_singleton(self, container):
        """Resolve a singleton."""
        service = DummyService("singleton")
        container.register_singleton(DummyService, service)
        resolved = container.resolve(DummyService)
        assert resolved.value == "singleton"

    def test_resolve_factory(self, container):
        """Resolve via factory."""
        container.register(DummyService, lambda: DummyService("factory"))
        resolved = container.resolve(DummyService)
        assert resolved.value == "factory"

    def test_resolve_cached(self, container):
        """Resolved factory instances are cached as singletons."""
        container.register(DummyService, lambda: DummyService("new"))
        first = container.resolve(DummyService)
        second = container.resolve(DummyService)
        assert first is second

    def test_resolve_unregistered_raises(self, container):
        """Resolve unregistered type raises KeyError."""
        with pytest.raises(KeyError):
            container.resolve(DummyService)

    def test_clear(self, container):
        """Clear removes all registrations."""
        container.register(DummyService, lambda: DummyService())
        container.clear()
        with pytest.raises(KeyError):
            container.resolve(DummyService)


class TestGetContainer:
    """Test cases for get_container function."""

    def test_returns_container(self):
        """get_container returns DIContainer."""
        container = get_container()
        assert isinstance(container, DIContainer)

    def test_singleton(self):
        """get_container returns same instance."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2