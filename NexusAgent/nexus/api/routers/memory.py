"""NEXUS API — Memory layer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from nexus.memory.chroma_service import NexusMemoryService
from nexus.core.config import get_settings

router = APIRouter()


def _get_memory() -> NexusMemoryService:
    """Get memory service instance."""
    settings = get_settings()
    return NexusMemoryService(persist_dir=settings.chroma_persist_dir)


@router.post("/store")
async def store_memory(request: dict):
    """Store a memory entry."""
    try:
        mem = _get_memory()
        layer = request.get("layer", "knowledge")
        content = request.get("content", "")
        metadata = request.get("metadata", {})
        doc_id = mem.store(content=content, namespace=layer, metadata=metadata)
        return {"id": doc_id, "layer": layer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recall")
async def recall_memory(request: dict):
    """Recall memories from a layer."""
    try:
        mem = _get_memory()
        layer = request.get("layer", "knowledge")
        query = request.get("query", "")
        limit = request.get("limit", 5)
        results = mem.search(query=query, namespace=layer, top_k=limit)
        return {"results": results, "count": len(results.get("documents", [[]])[0])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def memory_stats():
    """Get memory layer statistics."""
    try:
        mem = _get_memory()
        counts = {}
        for layer in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
            try:
                col = mem._get_collection(layer)
                counts[layer] = col.count()
            except Exception:
                counts[layer] = 0
        return {"counts": counts, "total": sum(counts.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compact")
async def compact_memory():
    """Compact memory layers."""
    try:
        mem = _get_memory()
        mem.compact()
        return {"status": "compacted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_layer(request: dict):
    """Clear a specific memory layer."""
    layer = request.get("layer", "knowledge")
    try:
        mem = _get_memory()
        mem.clear_namespace(layer)
        return {"status": "cleared", "layer": layer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
