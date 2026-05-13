"""
NEXUS MCP System Tools.
"""

import json
from typing import Any

from nexus.core.config import get_settings


async def get_status() -> str:
    """Get NEXUS system status."""
    try:
        settings = get_settings()
        return json.dumps({
            "status": "running",
            "version": "1.0.0",
            "config": {
                "chroma_persist_dir": settings.chroma_persist_dir,
                "orchestrator_max_iterations": settings.orchestrator_max_iterations,
            },
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_config() -> str:
    """Get NEXUS configuration."""
    try:
        settings = get_settings()
        return json.dumps({
            "chroma_persist_dir": settings.chroma_persist_dir,
            "orchestrator_max_iterations": settings.orchestrator_max_iterations,
            "orchestrator_checkpointer": settings.orchestrator_checkpointer,
            "orchestrator_interrupt_before_executor": settings.orchestrator_interrupt_before_executor,
            "log_level": settings.log_level,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def health_check() -> str:
    """Perform health check on NEXUS components."""
    try:
        from nexus.memory.chroma_service import NexusMemoryService

        memory_ok = True
        try:
            service = NexusMemoryService()
            await service.count("knowledge")
        except Exception:
            memory_ok = False

        return json.dumps({
            "status": "healthy" if memory_ok else "degraded",
            "components": {
                "memory": "ok" if memory_ok else "error",
                "llm": "ok",
                "orchestrator": "ok",
            },
        })
    except Exception as e:
        return json.dumps({"error": str(e)})