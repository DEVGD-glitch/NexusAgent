"""
NEXUS MCP Memory Tools.
"""

import json
from typing import Any, Optional

from nexus.memory.chroma_service import NexusMemoryService


async def search_memory(query: str, namespace: str = "conversations", top_k: int = 5) -> str:
    """Search memory for relevant content."""
    try:
        service = NexusMemoryService()
        results = await service.search(query, namespace, top_k)
        return json.dumps({"results": results, "query": query, "namespace": namespace})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def store_memory(text: str, namespace: str = "conversations", metadata: Optional[dict] = None) -> str:
    """Store content in memory."""
    try:
        service = NexusMemoryService()
        doc_id = await service.store(text, namespace, metadata or {})
        return json.dumps({"status": "stored", "doc_id": doc_id, "namespace": namespace})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def delete_memory(doc_ids: list[str], namespace: str = "conversations") -> str:
    """Delete content from memory."""
    try:
        service = NexusMemoryService()
        await service.delete(doc_ids, namespace)
        return json.dumps({"status": "deleted", "doc_ids": doc_ids, "namespace": namespace})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_namespaces() -> str:
    """List all available memory namespaces."""
    from nexus.memory.chroma_service import VALID_NAMESPACES
    return json.dumps({"namespaces": sorted(VALID_NAMESPACES)})


async def memory_stats() -> str:
    """Get memory usage statistics."""
    try:
        service = NexusMemoryService()
        stats = await service.get_stats()
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})