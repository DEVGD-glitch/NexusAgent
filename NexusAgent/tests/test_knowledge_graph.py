"""
Tests for nexus.knowledge.knowledge_graph.
"""

import pytest
from nexus.knowledge.knowledge_graph import KnowledgeGraph


class TestKnowledgeGraph:
    """Test cases for KnowledgeGraph class."""

    @pytest.fixture
    def graph(self):
        return KnowledgeGraph()

    def test_init(self, graph):
        """KnowledgeGraph initialization."""
        assert graph.graph is not None
        assert len(graph._entity_index) == 0
        assert len(graph._rel_type_index) == 0

    def test_add_entity(self, graph):
        """Add entity to graph."""
        node_id = graph.add_entity("Python", entity_type="language")
        assert node_id is not None
        assert "Python" in graph._entity_index

    def test_add_entity_with_properties(self, graph):
        """Add entity with properties."""
        props = {"paradigm": "multi", "created": 1991}
        node_id = graph.add_entity("Python", properties=props)
        assert node_id is not None

    def test_add_relationship(self, graph):
        """Add relationship between entities."""
        graph.add_entity("Alice", entity_type="person")
        graph.add_entity("Bob", entity_type="person")
        rel_id = graph.add_relationship("Alice", "Bob", "knows")
        assert rel_id is not None

    def test_get_entity(self, graph):
        """Get entity by name."""
        graph.add_entity("TestEntity", entity_type="test")
        entity = graph.get_entity("TestEntity")
        assert entity is not None

    def test_search_entities(self, graph):
        """Search entities."""
        graph.add_entity("Entity1", entity_type="person")
        graph.add_entity("Entity2", entity_type="person")
        graph.add_entity("Entity3", entity_type="place")
        results = graph.search_entities("Entity")
        assert len(results) >= 1

    def test_find_paths(self, graph):
        """Find paths between entities."""
        graph.add_entity("A", entity_type="test")
        graph.add_entity("B", entity_type="test")
        graph.add_entity("C", entity_type="test")
        graph.add_relationship("A", "B", "links")
        graph.add_relationship("B", "C", "links")
        paths = graph.find_paths("A", "C")
        assert paths is not None

    def test_get_neighbors(self, graph):
        """Get neighboring entities."""
        graph.add_entity("Node1", entity_type="test")
        graph.add_entity("Node2", entity_type="test")
        graph.add_relationship("Node1", "Node2", "related")
        neighbors = graph.get_neighbors("Node1")
        assert len(neighbors) >= 1