"""
NEXUS MCP Knowledge Graph Tools.
"""

import json
from typing import Any, Optional

from nexus.knowledge.knowledge_graph import KnowledgeGraph


async def knowledge_query(entity_name: str, depth: int = 1) -> str:
    """Query knowledge graph for entity and its connections."""
    try:
        kg = KnowledgeGraph()
        entity = kg.get_entity(entity_name)
        rels = kg.get_relationships(entity_name)
        neighbors = kg.get_neighbors(entity_name, degree=depth)
        return json.dumps({"entity": entity_name, "depth": depth, "entity_data": entity, "relationships": rels, "neighbors": neighbors})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def knowledge_add_entity(
    entity_type: str,
    name: str,
    properties: Optional[dict[str, Any]] = None,
) -> str:
    """Add an entity to the knowledge graph."""
    try:
        kg = KnowledgeGraph()
        entity_id = kg.add_entity(name, entity_type=entity_type, properties=properties or {})
        return json.dumps({"status": "added", "entity_id": entity_id, "type": entity_type, "name": name})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def knowledge_add_relation(
    source: str,
    target: str,
    relation_type: str,
    properties: Optional[dict[str, Any]] = None,
) -> str:
    """Add a relation between two entities."""
    try:
        kg = KnowledgeGraph()
        kg.add_relationship(source, target, relation_type)
        return json.dumps({"status": "added", "source": source, "target": target, "type": relation_type})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def knowledge_search(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Search the knowledge graph."""
    try:
        kg = KnowledgeGraph()
        results = kg.search_entities(query, entity_type, limit)
        return json.dumps({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def knowledge_paths(
    source_name: str,
    target_name: str,
    max_length: int = 5,
) -> str:
    """Find paths between two entities."""
    try:
        kg = KnowledgeGraph()
        paths = kg.find_paths(source_name, target_name, max_length)
        return json.dumps({"source": source_name, "target": target_name, "paths": paths, "count": len(paths)})
    except Exception as e:
        return json.dumps({"error": str(e)})