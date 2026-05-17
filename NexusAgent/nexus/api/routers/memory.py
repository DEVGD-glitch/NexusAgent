"""NEXUS API — Memory layer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from nexus.api.models import MemoryStoreRequest, MemoryRecallRequest
from nexus.memory.chroma_service import get_memory_service

router = APIRouter()


@router.post("/store")
async def store_memory(request: MemoryStoreRequest):
    """Store a memory entry."""
    try:
        mem = get_memory_service()
        doc_id = mem.store(
            namespace=request.layer,
            content=request.content,
            metadata=request.metadata or {},
        )
        return {"id": doc_id, "layer": request.layer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recall")
async def recall_memory(request: MemoryRecallRequest):
    """Recall memories from a layer."""
    try:
        mem = get_memory_service()
        results = mem.search(
            namespace=request.layer,
            query=request.query,
            n_results=request.limit,
        )
        return {"results": results, "count": len(results.get("documents", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def memory_stats():
    """Get memory layer statistics."""
    try:
        mem = get_memory_service()
        counts = {}
        for layer in ["working", "episodic", "semantic", "procedural", "identity"]:
            try:
                col = mem.get_collection(layer)
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
        mem = get_memory_service()
        mem.compact()
        return {"status": "compacted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_layer(request: dict):
    """Clear a specific memory layer."""
    layer = request.get("layer", "working")
    try:
        mem = get_memory_service()
        mem.clear_namespace(layer)
        return {"status": "cleared", "layer": layer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
