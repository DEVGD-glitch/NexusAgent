"""
Complete tests for nexus.core.di - Dependency Injection Container.

Covers remaining lines: resolve_factory with parameters, resolve_cached
singleton verification, clear() removes cached instances, get_container()
returns singleton, reset_container() behavior, configure_container().
"""

import pytest
from unittest.mock import MagicMock, patch
from nexus.core.di import DIContainer, configure_container, get_container, reset_container


class DummyService:
    """Basic dummy service for testing."""
    def __init__(self, value="default"):
        self.value = value


class DummyServiceWithParams:
    """Dummy service with constructor parameters."""
    def __init__(self, name: str, count: int = 1):
        self.name = name
        self.count = count


class DummyCounter:
    """Tracks instance count to verify singleton behavior."""
    instances = 0

    def __init__(self):
        DummyCounter.instances += 1
        self.instance_num = DummyCounter.instances


class TestDIContainerComplete:
    """Complete tests for DIContainer — remaining uncovered paths."""

    @pytest.fixture(autouse=True)
    def reset_counter(self):
        DummyCounter.instances = 0
        yield

    @pytest.fixture
    def container(self):
        return DIContainer()

    # ── resolve_factory with parameters ─────────────────────────────

    def test_resolve_factory_with_captured_params(self, container):
        """Factory capturing parameters resolves correctly."""
        params = {"name": "test_service", "count": 42}
        container.register(
            DummyServiceWithParams,
            lambda: DummyServiceWithParams(**params),
        )
        resolved = container.resolve(DummyServiceWithParams)
        assert resolved.name == "test_service"
        assert resolved.count == 42

    def test_resolve_factory_using_closure(self, container):
        """Factory using closure context resolves."""
        value = "closure_value"
        container.register(DummyService, lambda: DummyService(value))
        resolved = container.resolve(DummyService)
        assert resolved.value == "closure_value"

    def test_resolve_factory_complex_lambda(self, container):
        """Factory captures context more than once correctly."""
        items = []
        container.register(
            DummyService,
            lambda: DummyService(f"item_{len(items)}")
        )
        # The factory creates a value that depends on list length
        # But since resolve caches as singleton, only one call
        resolved = container.resolve(DummyService)
        assert resolved.value in ("item_0", "item_1")  # depends on when items is mutated
        resolved_again = container.resolve(DummyService)
        assert resolved_again is resolved  # cached

    # ── resolve_cached singleton verification ───────────────────────

    def test_resolve_cached_factory_stored_as_singleton(self, container):
        """Factory-resolved instance is stored as singleton."""
        container.register(DummyService, lambda: DummyService("singleton"))
        first = container.resolve(DummyService)
        second = container.resolve(DummyService)
        assert first is second
        assert first.value == "singleton"

    def test_resolve_cached_factory_only_called_once(self, container):
        """Factory is only called once; subsequent returns are cached."""
        container.register(DummyCounter, DummyCounter)
        first = container.resolve(DummyCounter)
        second = container.resolve(DummyCounter)
        assert first is second
        assert first.instance_num == 1
        assert DummyCounter.instances == 1

    def test_resolve_singleton_takes_precedence(self, container):
        """Singleton registration takes precedence over factory."""
        factory_instance = DummyService("from_factory")
        singleton_instance = DummyService("from_singleton")
        container.register(DummyService, lambda: factory_instance)
        container.register_singleton(DummyService, singleton_instance)
        resolved = container.resolve(DummyService)
        assert resolved is singleton_instance
        assert resolved.value == "from_singleton"

    # ── clear() ─────────────────────────────────────────────────────

    def test_clear_removes_factories(self, container):
        """clear removes all factory registrations."""
        container.register(DummyService, lambda: DummyService())
        container.clear()
        with pytest.raises(KeyError):
            container.resolve(DummyService)

    def test_clear_removes_singletons(self, container):
        """clear removes all singleton instances."""
        service = DummyService("persistent")
        container.register_singleton(DummyService, service)
        container.clear()
        with pytest.raises(KeyError):
            container.resolve(DummyService)

    def test_clear_removes_both_factories_and_singletons(self, container):
        """clear removes both factories and singletons."""
        container.register(DummyService, lambda: DummyService("factory"))
        container.register_singleton(DummyServiceWithParams, DummyServiceWithParams("s", 1))
        assert DummyService in container._factories
        assert DummyServiceWithParams in container._singletons
        container.clear()
        assert len(container._factories) == 0
        assert len(container._singletons) == 0

    def test_clear_empty_container(self, container):
        """clear on empty container does not raise."""
        container.clear()  # should not raise
        assert len(container._factories) == 0
        assert len(container._singletons) == 0

    def test_clear_then_reregister(self, container):
        """After clear, new registrations work correctly."""
        container.register(DummyService, lambda: DummyService("first"))
        container.clear()
        container.register(DummyService, lambda: DummyService("second"))
        resolved = container.resolve(DummyService)
        assert resolved.value == "second"

    # ── get_container() returns singleton ───────────────────────────

    def test_get_container_returns_singleton(self):
        """get_container always returns the same DIContainer instance."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2
        assert isinstance(c1, DIContainer)

    def test_get_container_multiple_calls_same_type(self):
        """get_container returns DIContainer type across calls."""
        c1 = get_container()
        c2 = get_container()
        assert type(c1) is DIContainer
        assert type(c2) is DIContainer

    # ── reset_container() ───────────────────────────────────────────

    def test_reset_container_creates_new(self):
        """reset_container clears global and makes get_container create new."""
        container = get_container()
        container.register(DummyService, lambda: DummyService("old"))

        reset_container()

        new_container = get_container()
        assert new_container is not container
        with pytest.raises(KeyError):
            new_container.resolve(DummyService)

    def test_reset_container_after_registration(self):
        """reset_container clears all prior registrations."""
        container = get_container()
        container.register(DummyService, lambda: DummyService("before"))

        reset_container()

        new_container = get_container()
        new_container.register(DummyService, lambda: DummyService("after"))
        resolved = new_container.resolve(DummyService)
        assert resolved.value == "after"

    def test_reset_container_twice(self):
        """Calling reset_container twice does not raise."""
        reset_container()
        reset_container()  # second call should not raise
        container = get_container()
        assert isinstance(container, DIContainer)

    def test_reset_container_clears_old_container(self):
        """reset_container clears registrations from old container."""
        old_container = get_container()
        old_container.register(DummyService, lambda: DummyService("survivor"))

        # resolve to verify registration works before reset
        resolved_before = old_container.resolve(DummyService)
        assert resolved_before.value == "survivor"

        reset_container()
        # reset_container calls _container.clear(), wiping the old one
        with pytest.raises(KeyError):
            old_container.resolve(DummyService)

        # The global is now a new container
        new_container = get_container()
        assert new_container is not old_container


class TestConfigureContainer:
    """Tests for configure_container function — covers lines 65-87."""

    @patch("nexus.security.audit.AuditLogger")
    @patch("nexus.security.guardrails.Guardrails", create=True)
    @patch("nexus.knowledge.knowledge_graph.KnowledgeGraph")
    @patch("nexus.memory.chroma_service.NexusMemoryService")
    @patch("nexus.core.config.get_settings")
    def test_configure_container_registers_all(
        self,
        mock_get_settings,
        MockMemoryService,
        MockKnowledgeGraph,
        MockGuardrails,
        MockAuditLogger,
    ):
        """configure_container registers all expected services."""
        mock_settings = MagicMock()
        mock_settings.chroma_persist_dir = "/tmp/test/chroma"
        mock_get_settings.return_value = mock_settings

        reset_container()
        try:
            configure_container()

            container = get_container()
            # Should have 4 registered factories
            assert len(container._factories) == 4
            # Each mock class is the key in _factories
            assert MockMemoryService in container._factories
            assert MockKnowledgeGraph in container._factories
            assert MockGuardrails in container._factories
            assert MockAuditLogger in container._factories
        finally:
            reset_container()

    @patch("nexus.security.audit.AuditLogger")
    @patch("nexus.security.guardrails.Guardrails", create=True)
    @patch("nexus.knowledge.knowledge_graph.KnowledgeGraph")
    @patch("nexus.memory.chroma_service.NexusMemoryService")
    @patch("nexus.core.config.get_settings")
    def test_configure_container_resolves_memory(
        self,
        mock_get_settings,
        MockMemoryService,
        MockKnowledgeGraph,
        MockGuardrails,
        MockAuditLogger,
    ):
        """Memory service factory uses chroma_persist_dir from settings."""
        mock_settings = MagicMock()
        mock_settings.chroma_persist_dir = "/custom/chroma/path"
        mock_get_settings.return_value = mock_settings

        reset_container()
        try:
            configure_container()
            container = get_container()

            # Resolve memory service — factory calls NexusMemoryService(persist_dir=...)
            resolved = container.resolve(MockMemoryService)
            MockMemoryService.assert_called_once_with(
                persist_dir="/custom/chroma/path"
            )
        finally:
            reset_container()

    @patch("nexus.security.audit.AuditLogger")
    @patch("nexus.security.guardrails.Guardrails", create=True)
    @patch("nexus.knowledge.knowledge_graph.KnowledgeGraph")
    @patch("nexus.memory.chroma_service.NexusMemoryService")
    @patch("nexus.core.config.get_settings")
    def test_configure_container_knowledge_graph_as_factory(
        self,
        mock_get_settings,
        MockMemoryService,
        MockKnowledgeGraph,
        MockGuardrails,
        MockAuditLogger,
    ):
        """KnowledgeGraph is registered as its own factory."""
        mock_settings = MagicMock()
        mock_settings.chroma_persist_dir = "/tmp/chroma"
        mock_get_settings.return_value = mock_settings

        reset_container()
        try:
            configure_container()
            container = get_container()

            # KnowledgeGraph is registered as both key and factory
            assert container._factories[MockKnowledgeGraph] is MockKnowledgeGraph
            resolved = container.resolve(MockKnowledgeGraph)
            MockKnowledgeGraph.assert_called_once()
        finally:
            reset_container()
