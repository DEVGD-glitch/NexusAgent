"""
[DEPRECATED] NEXUS Gateway — use nexus.api.gateway instead.

This module is a legacy duplicate kept for backward compatibility.
All new development should use nexus.api.gateway (the main gateway).

Differences from nexus.api.gateway:
  - Fewer endpoints (no tools, knowledge, agents, code execution)
  - Simpler request models
  - No audit logging
  - No path traversal protection on all endpoints

Will be removed in a future release. Import from nexus.api.gateway instead.

Provides the primary HTTP interface to NEXUS:
  - GET  /health          : Health check
  - POST /run             : Run a task through the orchestrator
  - POST /chat            : Chat completion endpoint
  - WS   /ws/chat         : WebSocket chat interface
  - GET  /status          : Agent status
  - GET  /providers       : LLM provider status
  - GET  /memory/stats    : Memory statistics
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)
logger.warning(
    "nexus.core.gateway is DEPRECATED. Use nexus.api.gateway instead. "
    "This module will be removed in a future release."
)

# ── Path Traversal Protection ───────────────────────────────────

def _get_working_dir() -> Path:
    """Get the configured working directory."""
    from pathlib import Path
    settings = get_settings()
    return Path(settings.nexus_working_dir).resolve()


def _safe_path(path: str, working_dir: Path) -> Path | None:
    """
    Resolve path and verify it's within working_dir.
    Returns resolved Path if safe, None if path traversal detected.
    """
    from pathlib import Path
    try:
        resolved = Path(path).resolve()
        working = working_dir.resolve()
        resolved.relative_to(working)
        return resolved
    except (ValueError, OSError):
        return None


# ── FastAPI App ───────────────────────────────────────────────────

app = FastAPI(
    title="NEXUS Agent API",
    description="Universal Sovereign AI Agent — REST + WebSocket API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web frontend
_frontend_origins = os.getenv("NEXUS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# ── Request/Response Models ───────────────────────────────────────

class RunRequest(BaseModel):
    """Request to run a task through NEXUS."""
    task: str = Field(..., description="Task description", min_length=1)
    provider: Optional[str] = Field(None, description="Preferred LLM provider")
    complexity: Optional[str] = Field(None, description="Task complexity: simple, medium, complex")
    thread_id: Optional[str] = Field(None, description="Thread ID for session continuity")
    context: Optional[list[dict[str, str]]] = Field(None, description="Prior conversation messages")


class RunResponse(BaseModel):
    """Response from a task run."""
    task: str
    result: str
    plan: str = ""
    reflection: str = ""
    iterations: int = 0
    thread_id: str = ""
    status: str = "completed"
    latency_ms: float = 0.0


class ChatRequest(BaseModel):
    """Chat completion request."""
    messages: list[dict[str, str]] = Field(..., description="Chat messages")
    model: Optional[str] = Field(None, description="Model name")
    provider: Optional[str] = Field(None, description="Provider name")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=128000)


class ChatResponse(BaseModel):
    """Chat completion response."""
    content: str
    provider: str
    model: str
    usage: dict[str, int] = {}
    latency_ms: float = 0.0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"
    uptime_seconds: float = 0.0


# ── Startup Time ──────────────────────────────────────────────────

_start_time = time.time()


# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.nexus_env.value,
        uptime_seconds=time.time() - _start_time,
    )


@app.post("/run", response_model=RunResponse)
async def run_task(request: RunRequest):
    """
    Run a task through the NEXUS Plan-Execute-Reflect orchestrator.

    This is the primary endpoint for executing complex tasks.
    The agent will plan, execute, and reflect on the task
    automatically.
    """
    start = time.monotonic()

    try:
        from nexus.orchestrator.langgraph_engine import run_nexus_task
        result = await run_nexus_task(
            task=request.task,
            messages=request.context or [],
            thread_id=request.thread_id,
        )

        latency = (time.monotonic() - start) * 1000

        return RunResponse(
            task=request.task,
            result=result.get("result", ""),
            plan=result.get("plan", ""),
            reflection=result.get("reflection", ""),
            iterations=result.get("iterations", 0),
            thread_id=result.get("thread_id", ""),
            status=result.get("status", "completed"),
            latency_ms=latency,
        )
    except Exception as exc:
        logger.error("Task execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """
    Direct chat completion endpoint — single LLM call without orchestration.

    Use this for simple queries that don't need the full
    Plan-Execute-Reflect loop.
    """
    start = time.monotonic()

    try:
        from nexus.llm.router import LLMRouter, TaskComplexity
        router = LLMRouter()

        complexity = TaskComplexity.SIMPLE
        response = await router.complete(
            messages=request.messages,
            model=request.model,
            provider=request.provider,
            task_complexity=complexity,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        latency = (time.monotonic() - start) * 1000

        return ChatResponse(
            content=response.content,
            provider=response.provider.value,
            model=response.model,
            usage=response.usage,
            latency_ms=latency,
        )
    except Exception as exc:
        logger.error("Chat completion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/status")
async def get_status():
    """Get NEXUS agent status and configuration."""
    settings = get_settings()
    return {
        "agent": "NEXUS",
        "version": "0.1.0",
        "status": "running",
        "environment": settings.nexus_env.value,
        "uptime_seconds": time.time() - _start_time,
        "providers_configured": settings.available_providers,
    }


@app.get("/providers")
async def get_providers():
    """Get LLM provider status and configuration."""
    try:
        from nexus.llm.router import LLMRouter
        router = LLMRouter()
        return router.get_provider_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/memory/stats")
async def get_memory_stats():
    """Get memory statistics across all namespaces."""
    try:
        from nexus.memory.chroma_service import NexusMemoryService
        from nexus.memory.episodic import EpisodicMemory
        from nexus.memory.semantic import SemanticMemory
        from nexus.memory.procedural import ProceduralMemory
        from nexus.memory.identity import IdentityMemory

        settings = get_settings()
        service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)

        stats = {}
        for ns in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
            try:
                count = await service.count(namespace=ns)
                stats[ns] = {"count": count}
            except Exception:
                stats[ns] = {"count": 0, "error": "namespace not accessible"}

        return {"namespaces": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket ─────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with NEXUS."""
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    logger.info("WebSocket session %s connected", session_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                user_content = message.get("content", "")
            except json.JSONDecodeError:
                user_content = data

            if not user_content.strip():
                continue

            try:
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()
                response = await router.complete(
                    messages=[{"role": "user", "content": user_content}],
                    task_complexity=TaskComplexity.SIMPLE,
                )

                await websocket.send_json({
                    "type": "response",
                    "content": response.content,
                    "provider": response.provider.value,
                    "model": response.model,
                    "session_id": session_id,
                })
            except Exception as exc:
                await websocket.send_json({
                    "type": "error",
                    "content": str(exc),
                    "session_id": session_id,
                })

    except WebSocketDisconnect:
        logger.info("WebSocket session %s disconnected", session_id)
