"""
NEXUS Knowledge Graph — L4 Entity-Relationship graph using NetworkX.

Implements a knowledge graph layer that stores entities and their
relationships as a directed graph. Complements the vector memory
by providing structured, queryable relationships between concepts.

Based on APEX's L4 Knowledge Graph specification.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    L4 Knowledge Graph — Entity-Relationship graph for NEXUS.

    Uses NetworkX DiGraph to store:
      - Entities as nodes (with type, properties, embeddings)
      - Relationships as directed edges (with type, weight, metadata)
      - Temporal information (when relationships were established)
      - Provenance (source of each fact)

    Supports:
      - Add/remove/query entities
      - Add/remove/query relationships
      - Path finding between entities
      - Subgraph extraction
      - Graph statistics and analysis
      - Export to multiple formats

    Usage:
        kg = KnowledgeGraph()
        kg.add_entity("Python", entity_type="language", properties={"paradigm": "multi"})
        kg.add_entity("Guido van Rossum", entity_type="person")
        kg.add_relationship("Guido van Rossum", "Python", "created")
        paths = kg.find_paths("Guido van Rossum", "Python")
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._entity_index: dict[str, str] = {}  # name -> node_id
        self._rel_type_index: dict[str, list[tuple[str, str]]] = {}  # rel_type -> [(src, tgt)]

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        properties: Optional[dict[str, Any]] = None,
        source: str = "user",
        confidence: float = 1.0,
    ) -> str:
        """
        Add an entity to the knowledge graph.

        Args:
            name: Entity name/identifier.
            entity_type: Type of entity (person, concept, tool, etc.).
            properties: Additional properties.
            source: Origin of this entity.
            confidence: Confidence score 0-1.

        Returns:
            Node ID of the entity.
        """
        # Check if entity already exists
        if name in self._entity_index:
            node_id = self._entity_index[name]
            # Update existing entity immutably
            existing = self.graph.nodes[node_id]
            new_properties = {**(existing.get("properties", {})), **(properties or {})}
            new_properties["updated_at"] = datetime.now(timezone.utc).isoformat()
            new_node_data = dict(existing)
            new_node_data["properties"] = new_properties
            new_node_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            new_node_data["confidence"] = max(existing.get("confidence", 0), confidence)
            self.graph.nodes[node_id].update(new_node_data)
            logger.debug("Updated entity: %s", name)
            return node_id

        node_id = f"entity_{uuid.uuid4().hex[:8]}"
        self._entity_index[name] = node_id

        self.graph.add_node(
            node_id,
            name=name,
            entity_type=entity_type,
            properties=properties or {},
            source=source,
            confidence=confidence,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("Added entity: %s (type=%s)", name, entity_type)
        return node_id

    def add_relationship(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        properties: Optional[dict[str, Any]] = None,
        weight: float = 1.0,
        bidirectional: bool = False,
    ) -> bool:
        """
        Add a relationship between two entities.

        Args:
            source_name: Source entity name.
            target_name: Target entity name.
            relation_type: Type of relationship.
            properties: Additional edge properties.
            weight: Edge weight (higher = stronger relationship).
            bidirectional: If True, also add reverse edge.

        Returns:
            True if the relationship was added.
        """
        # Ensure entities exist
        if source_name not in self._entity_index:
            self.add_entity(source_name)
        if target_name not in self._entity_index:
            self.add_entity(target_name)

        src_id = self._entity_index[source_name]
        tgt_id = self._entity_index[target_name]

        edge_data = {
            "relation_type": relation_type,
            "weight": weight,
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.graph.add_edge(src_id, tgt_id, **edge_data)

        # Index by relation type
        if relation_type not in self._rel_type_index:
            self._rel_type_index[relation_type] = []
        self._rel_type_index[relation_type].append((src_id, tgt_id))

        if bidirectional:
            reverse_data = dict(edge_data)
            reverse_data["relation_type"] = f"{relation_type}_reverse"
            self.graph.add_edge(tgt_id, src_id, **reverse_data)

        logger.info("Added relationship: %s --[%s]--> %s", source_name, relation_type, target_name)
        return True

    def get_entity(self, name: str) -> Optional[dict[str, Any]]:
        """Get an entity by name."""
        node_id = self._entity_index.get(name)
        if node_id and node_id in self.graph.nodes:
            return dict(self.graph.nodes[node_id])
        return None

    def get_relationships(
        self,
        name: str,
        relation_type: Optional[str] = None,
        direction: str = "both",  # "outgoing", "incoming", "both"
    ) -> list[dict[str, Any]]:
        """
        Get relationships for an entity.

        Args:
            name: Entity name.
            relation_type: Filter by relationship type.
            direction: Direction of relationships to return.

        Returns:
            List of relationship dicts.
        """
        node_id = self._entity_index.get(name)
        if not node_id:
            return []

        results = []

        if direction in ("outgoing", "both"):
            for _, target, data in self.graph.out_edges(node_id, data=True):
                if relation_type and data.get("relation_type") != relation_type:
                    continue
                target_name = self.graph.nodes[target].get("name", target)
                results.append({
                    "source": name,
                    "target": target_name,
                    "relation_type": data["relation_type"],
                    "weight": data.get("weight", 1.0),
                    "properties": data.get("properties", {}),
                })

        if direction in ("incoming", "both"):
            for source, _, data in self.graph.in_edges(node_id, data=True):
                if relation_type and data.get("relation_type") != relation_type:
                    continue
                source_name = self.graph.nodes[source].get("name", source)
                results.append({
                    "source": source_name,
                    "target": name,
                    "relation_type": data["relation_type"],
                    "weight": data.get("weight", 1.0),
                    "properties": data.get("properties", {}),
                })

        return results

    def find_paths(
        self,
        source_name: str,
        target_name: str,
        max_length: int = 5,
    ) -> list[list[str]]:
        """
        Find all paths between two entities.

        Args:
            source_name: Source entity.
            target_name: Target entity.
            max_length: Maximum path length.

        Returns:
            List of paths, where each path is a list of entity names.
        """
        src_id = self._entity_index.get(source_name)
        tgt_id = self._entity_index.get(target_name)

        if not src_id or not tgt_id:
            return []

        try:
            node_paths = nx.all_simple_paths(
                self.graph, src_id, tgt_id, cutoff=max_length
            )
            name_paths = []
            for path in node_paths:
                name_path = [self.graph.nodes[n].get("name", n) for n in path]
                name_paths.append(name_path)
            return name_paths
        except nx.NetworkXNoPath:
            return []

    def get_neighbors(
        self,
        name: str,
        degree: int = 1,
    ) -> list[str]:
        """Get neighboring entities up to a given degree."""
        node_id = self._entity_index.get(name)
        if not node_id:
            return []

        visited = {node_id}
        current_level = {node_id}

        for _ in range(degree):
            next_level = set()
            for n in current_level:
                for neighbor in self.graph.neighbors(n):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
                for neighbor in self.graph.predecessors(n):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level

        visited.discard(node_id)
        return [self.graph.nodes[n].get("name", n) for n in visited]

    def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search entities by name (simple text matching)."""
        query_lower = query.lower()
        results = []

        for node_id, data in self.graph.nodes(data=True):
            name = data.get("name", "")
            if query_lower in name.lower():
                if entity_type and data.get("entity_type") != entity_type:
                    continue
                results.append({"node_id": node_id, **data})
                if len(results) >= limit:
                    break

        return results

    def get_subgraph(
        self,
        center_name: str,
        radius: int = 2,
    ) -> dict[str, Any]:
        """Extract a subgraph around an entity."""
        node_id = self._entity_index.get(center_name)
        if not node_id:
            return {"nodes": [], "edges": []}

        # BFS to find nodes within radius
        visited = {node_id}
        current_level = {node_id}

        for _ in range(radius):
            next_level = set()
            for n in current_level:
                for neighbor in self.graph.neighbors(n):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
                for neighbor in self.graph.predecessors(n):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level

        subgraph = self.graph.subgraph(visited)

        nodes = [{"id": n, **data} for n, data in subgraph.nodes(data=True)]
        edges = [
            {
                "source": self.graph.nodes[s].get("name", s),
                "target": self.graph.nodes[t].get("name", t),
                "relation_type": d.get("relation_type", ""),
                "weight": d.get("weight", 1.0),
            }
            for s, t, d in subgraph.edges(data=True)
        ]

        return {"nodes": nodes, "edges": edges}

    def remove_entity(self, name: str) -> bool:
        """Remove an entity and all its relationships."""
        node_id = self._entity_index.get(name)
        if not node_id:
            return False
        self.graph.remove_node(node_id)
        del self._entity_index[name]
        logger.info("Removed entity: %s", name)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge graph statistics."""
        return {
            "total_entities": self.graph.number_of_nodes(),
            "total_relationships": self.graph.number_of_edges(),
            "entity_types": list(set(
                d.get("entity_type", "unknown")
                for _, d in self.graph.nodes(data=True)
            )),
            "relation_types": list(self._rel_type_index.keys()),
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else True,
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0.0,
        }

    # Default persistence path
    _PERSIST_PATH: str = "./nexus_data/knowledge_graph.json"

    def save(self, path: Optional[str] = None) -> bool:
        """
        Persist the knowledge graph to a JSON file.

        Args:
            path: File path. Defaults to ./nexus_data/knowledge_graph.json.

        Returns:
            True if saved successfully.
        """
        try:
            save_path = Path(path or self._PERSIST_PATH)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            data = nx.node_link_data(self.graph)
            save_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            logger.info("Knowledge graph saved (%d nodes, %d edges) to %s",
                        self.graph.number_of_nodes(), self.graph.number_of_edges(), save_path)
            return True
        except Exception as exc:
            logger.error("Failed to save knowledge graph: %s", exc)
            return False

    def load(self, path: Optional[str] = None) -> bool:
        """
        Load the knowledge graph from a JSON file.

        Args:
            path: File path. Defaults to ./nexus_data/knowledge_graph.json.

        Returns:
            True if loaded successfully, False if file not found or invalid.
        """
        try:
            load_path = Path(path or self._PERSIST_PATH)
            if not load_path.exists():
                logger.info("No persisted knowledge graph found at %s", load_path)
                return False
            data = json.loads(load_path.read_text(encoding="utf-8"))
            self.graph = nx.node_link_graph(data, directed=True)
            # Rebuild entity index
            self._entity_index = {}
            for node_id, node_data in self.graph.nodes(data=True):
                name = node_data.get("name", "")
                if name:
                    self._entity_index[name] = node_id
            logger.info("Knowledge graph loaded (%d nodes, %d edges) from %s",
                        self.graph.number_of_nodes(), self.graph.number_of_edges(), load_path)
            return True
        except Exception as exc:
            logger.error("Failed to load knowledge graph: %s", exc)
            return False

    def export_to_json(self) -> str:
        """Export the graph as JSON."""
        data = nx.node_link_data(self.graph)
        return json.dumps(data, indent=2, default=str)

    def import_from_json(self, json_str: str) -> int:
        """Import a graph from JSON. Returns number of nodes imported."""
        data = json.loads(json_str)
        self.graph = nx.node_link_graph(data, directed=True)
        # Rebuild entity index
        self._entity_index = {}
        for node_id, node_data in self.graph.nodes(data=True):
            name = node_data.get("name", "")
            if name:
                self._entity_index[name] = node_id
        return self.graph.number_of_nodes()
