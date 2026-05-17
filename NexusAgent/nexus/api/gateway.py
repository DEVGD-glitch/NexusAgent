"""
NEXUS FastAPI Gateway — Complete REST API for the Next.js frontend.

Exposes all NEXUS capabilities through a unified HTTP API that the
Next.js frontend proxies via /api/nexus/* → http://localhost:8080/*.

Design principles:
  - Lazy imports: heavy modules (chromadb, networkx, etc.) loaded only when needed
  - Windows-compatible: no Unix-only features (no resource module, no signals)
  - Explicit provider choice: no silent fallback, frontend handles toast confirmations
  - Lightweight audit logging for every action
  - Human-readable error messages in all responses
  - CORS enabled for the Next.js frontend
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from nexus.api.auth import verify_auth, verify_ws_auth

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Event Broadcaster — lazy-loaded singleton
# ═══════════════════════════════════════════════════════════════════

def _get_broadcaster():
    """Lazy-load the EventBroadcaster singleton."""
    from nexus.core.events import get_broadcaster
    broadcaster = get_broadcaster()
    # Wire up the VizEventEmitter with the broadcaster so viz events
    # are streamed to all WebSocket subscribers in real-time.
    try:
        from nexus.core.viz_events import get_viz_emitter
        emitter = get_viz_emitter()
        if emitter._broadcaster is None:
            emitter.set_broadcaster(broadcaster)
    except Exception:
        pass
    return broadcaster


# ═══════════════════════════════════════════════════════════════════
# Security helpers
# ═══════════════════════════════════════════════════════════════════

_WEAK_SECRET_KEYS = frozenset({
    "dev-test-key-not-for-production",
    "change-me-to-a-secure-random-string",
    "",
})


def _warn_default_key():
    """Emit a single warning if NEXUS_SECRET_KEY is a weak/default value."""
    from nexus.core.config import get_settings
    sk = get_settings().nexus_secret_key
    if sk in _WEAK_SECRET_KEYS or len(sk) < 16:
        logger.warning(
            "NEXUS_SECRET_KEY is weak or default. "
            "Generate a strong random key with: python -c \"import secrets; print(secrets.token_hex(32))\"",
        )


# ═══════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════

_nexus_env_raw = os.getenv("NEXUS_ENV", "development")
_is_production = _nexus_env_raw.lower() == "production"

app = FastAPI(
    title="NEXUS Agent Gateway",
    description="Universal Sovereign AI Agent — REST API Gateway for Next.js frontend",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    dependencies=[Depends(verify_auth)],
)

_warn_default_key()

# ── Include Voice API Routes ────────────────────────────────────
try:
    from nexus.api.voice_routes import router as voice_router
    app.include_router(voice_router)
    logger.info("[Gateway] Voice API routes included (/voice/*)")
except Exception as _voice_import_err:
    logger.warning("[Gateway] Voice API routes not available: %s", _voice_import_err)

# ── Include MCP Marketplace API Routes ─────────────────────────
try:
    from nexus.mcp.api import router as mcp_router
    app.include_router(mcp_router)
    logger.info("[Gateway] MCP Marketplace API routes included (/api/mcp/*, /api/tools/*)")
except Exception as _mcp_import_err:
    logger.warning("[Gateway] MCP Marketplace API routes not available: %s", _mcp_import_err)

# CORS middleware — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Rate Limiter ────────────────────────────────────────────────

_limiter = None


def _get_limiter():
    global _limiter
    if _limiter is None:
        from nexus.security.rate_limiter import RateLimiter
        _limiter = RateLimiter()
    return _limiter


# ── Rate Limiter Middleware ───────────────────────────────────────
# Auth is handled globally by the verify_auth dependency above.

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Enforce rate limits on all HTTP requests."""
    client_ip = request.client.host if request.client else "unknown"
    try:
        _get_limiter().check(client_ip, action="api_call", tokens=1)
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please wait before making more requests."},
        )
    return await call_next(request)


# Track server start time
_START_TIME = time.time()


# ═══════════════════════════════════════════════════════════════════
# Path Traversal Protection
# ═══════════════════════════════════════════════════════════════════

def _get_working_dir() -> Path:
    """Get the configured working directory."""
    from nexus.core.config import get_settings
    return Path(get_settings().nexus_working_dir).resolve()


def _safe_path(path: str, working_dir: Path) -> Path | None:
    """
    Resolve path and verify it's within working_dir.
    Returns resolved Path if safe, None if path traversal detected.
    """
    try:
        resolved = Path(path).resolve()
        working = working_dir.resolve()
        resolved.relative_to(working)
        return resolved
    except (ValueError, OSError):
        return None


# ═══════════════════════════════════════════════════════════════════
# Lazy Singletons — instantiated on first use, not at import time
# ═══════════════════════════════════════════════════════════════════

_router = None
_memory_service = None
_audit_logger = None
_knowledge_graph = None
_memory_orchestrator = None
_episodic_memory = None
_semantic_memory = None
_procedural_memory = None
_identity_memory = None
_memory_compactor = None
_skill_lifecycle = None
_scheduled_crons: dict[str, dict[str, Any]] = {}


def _get_router():
    """Lazy-load the LLM router."""
    global _router
    if _router is None:
        from nexus.llm.router import LLMRouter
        _router = LLMRouter()
    return _router


def _get_memory_service():
    """Lazy-load the ChromaDB memory service."""
    global _memory_service
    if _memory_service is None:
        from nexus.memory.chroma_service import NexusMemoryService
        from nexus.core.config import get_settings
        settings = get_settings()
        _memory_service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
    return _memory_service


def _get_audit_logger():
    """Lazy-load the audit logger."""
    global _audit_logger
    if _audit_logger is None:
        from nexus.security.audit import AuditLogger
        _audit_logger = AuditLogger()
    return _audit_logger


def _get_knowledge_graph():
    """Lazy-load the Knowledge Graph with persistence."""
    global _knowledge_graph
    if _knowledge_graph is None:
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        _knowledge_graph = KnowledgeGraph()
        _knowledge_graph.load()
    return _knowledge_graph


def _get_memory_orchestrator():
    """Lazy-load the Memory Orchestrator."""
    global _memory_orchestrator
    if _memory_orchestrator is None:
        from nexus.memory.orchestrator import MemoryOrchestrator, MemoryContext
        _memory_orchestrator = MemoryOrchestrator()
    return _memory_orchestrator


def _get_episodic_memory():
    """Lazy-load Episodic Memory."""
    global _episodic_memory
    if _episodic_memory is None:
        from nexus.memory.episodic import EpisodicMemory
        _episodic_memory = EpisodicMemory(memory_service=_get_memory_service())
    return _episodic_memory


def _get_semantic_memory():
    """Lazy-load Semantic Memory."""
    global _semantic_memory
    if _semantic_memory is None:
        from nexus.memory.semantic import SemanticMemory
        _semantic_memory = SemanticMemory(memory_service=_get_memory_service())
    return _semantic_memory


def _get_procedural_memory():
    """Lazy-load Procedural Memory."""
    global _procedural_memory
    if _procedural_memory is None:
        from nexus.memory.procedural import ProceduralMemory
        _procedural_memory = ProceduralMemory(memory_service=_get_memory_service())
    return _procedural_memory


def _get_identity_memory():
    """Lazy-load Identity Memory."""
    global _identity_memory
    if _identity_memory is None:
        from nexus.memory.identity import IdentityMemory
        _identity_memory = IdentityMemory(memory_service=_get_memory_service())
    return _identity_memory


def _get_memory_compactor():
    """Lazy-load the Memory Compactor."""
    global _memory_compactor
    if _memory_compactor is None:
        from nexus.memory.compactor import MemoryCompactor
        _memory_compactor = MemoryCompactor(memory_service=_get_memory_service())
    return _memory_compactor


def _get_skill_lifecycle():
    """Lazy-load the Skill Lifecycle Manager."""
    global _skill_lifecycle
    if _skill_lifecycle is None:
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        _skill_lifecycle = SkillLifecycleManager()
    return _skill_lifecycle


def _audit(action: str, target: str = "", details: Optional[dict] = None, outcome: str = "success"):
    """Log an action to the audit trail. Never raises — failures are silently ignored."""
    try:
        audit = _get_audit_logger()
        from nexus.security.audit import AuditCategory, AuditLevel
        audit.log(
            category=AuditCategory.AGENT_ACTION,
            action=action,
            target=target,
            details=details or {},
            outcome=outcome,
        )
    except Exception as exc:
        logger.debug("Audit logging failed: %s", exc)


def _safe_json_parse(text: str) -> Any:
    """Parse JSON string, returning the raw string on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# ═══════════════════════════════════════════════════════════════════
# Request / Response Models
# ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(..., description="Chat messages [{role, content}]")
    provider: Optional[str] = Field(None, description="Explicit provider: openai, anthropic, gemini, glm, ollama")
    model: Optional[str] = Field(None, description="Specific model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=128000)
    thinkingConfig: Optional[dict[str, Any]] = Field(None, description="Thinking config for Gemma 4 etc: {thinkingLevel, thinkingBudget}")


class RunRequest(BaseModel):
    task: str = Field(..., description="Task description", min_length=1)
    provider: Optional[str] = Field(None, description="Preferred LLM provider")
    strategy: Optional[str] = Field(None, description="Orchestration strategy: pipeline, parallel, swarm")


class CodeExecuteRequest(BaseModel):
    code: str = Field(..., description="Code to execute")
    language: str = Field("python", description="Programming language")
    timeout: int = Field(30, ge=1, le=300, description="Timeout in seconds")
    sandboxed: bool = Field(True, description="Run in sandbox")


class SpawnAgentRequest(BaseModel):
    task: str = Field(..., description="Task for the agent")
    agent_type: str = Field("general", description="Agent type: general, researcher, developer, analyst, operator")


# ═══════════════════════════════════════════════════════════════════
# 1. CHAT — POST /chat
# ═══════════════════════════════════════════════════════════════════

@app.post("/chat")
async def chat_completion(request: ChatRequest):
    """
    Chat completion endpoint — calls LLMRouter.complete() with explicit provider.

    No silent fallback: if the chosen provider fails, the error is returned
    so the frontend can show a toast and let the user pick another provider.
    Broadcasts real-time events via the EventBroadcaster.
    """
    start = time.monotonic()
    broadcaster = _get_broadcaster()
    try:
        from nexus.llm.router import TaskComplexity
        router = _get_router()

        # Broadcast: agent is thinking
        await broadcaster.broadcast("agent_thinking", {
            "action": "chat_completion",
            "provider": request.provider or "auto",
            "message_count": len(request.messages),
        })

        # Inject NEXUS awareness system prompt so the agent knows its capabilities
        SYSTEM_PROMPT = (
            "You are NEXUS, a sovereign AI agent. "
            "You have access to the following capabilities:\n"
            "- Memory: search_memory(query, namespace), store_memory(text, namespace) — vector knowledge base\n"
            "- Knowledge Graph: knowledge_query(entity), knowledge_search(query) — entity/relationship graph\n"
            "- Web Search: web_search(query, num_results) — real-time web information\n"
            "- Code Execution: execute_code(code, language, timeout, sandboxed) — run Python/JS/Bash\n"
            "- File System: read_file(path), write_file(path, content), list_files(directory)\n"
            "- Task Orchestration: spawn_agent(task, agent_type) — create sub-agents for complex tasks\n"
            "- Reasoning: reason_react(task), reason_tot(task) — structured reasoning\n"
            "- System: get_status(), audit_query(limit) — system information\n"
            "- Avatar/Voice: avatar_speak(text), avatar_set_expression(expression) — TTS and VRM control\n\n"
            "When a user asks a question, consider which tools would help answer it. "
            "For current information, use web_search. For complex tasks, create a plan using tasks. "
            "For code questions, you can use execute_code. "
            "Always respond in French unless the user asks otherwise."
        )

        # Prepend system message if not already present
        user_messages = list(request.messages)
        has_system = any(m.get("role") == "system" for m in user_messages)
        if not has_system:
            user_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_messages

        # If provider is explicitly set, use only that provider (no fallback)
        if request.provider:
            try:
                from nexus.llm.router import Provider
                Provider(request.provider)  # validate provider name
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown provider '{request.provider}'. Choose from: gemini, groq, openrouter, nvidia, cerebras, together, openai, anthropic, ollama, pollinations, g4f, deepinfra",
                )

        # Broadcast: tool call (LLM completion)
        await broadcaster.broadcast("tool_call", {
            "tool": "llm_complete",
            "provider": request.provider or "auto",
            "model": request.model or "default",
        })

        kwargs = {}
        if request.thinkingConfig:
            kwargs["thinking_config"] = request.thinkingConfig

        response = await router.complete(
            messages=user_messages,
            model=request.model,
            provider=request.provider,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **kwargs,
        )

        # Broadcast: tool result
        latency = (time.monotonic() - start) * 1000
        await broadcaster.broadcast("tool_result", {
            "tool": "llm_complete",
            "provider": response.provider.value,
            "model": response.model,
            "latency_ms": latency,
            "usage": response.usage,
        })

        # Broadcast: agent action complete
        await broadcaster.broadcast("agent_action", {
            "action": "chat_response",
            "provider": response.provider.value,
            "model": response.model,
            "content_length": len(response.content),
        })

        _audit("chat", target=request.provider or "auto", details={"latency_ms": latency})

        return {
            "content": response.content,
            "provider": response.provider.value,
            "model": response.model,
            "usage": response.usage,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat completion failed: %s", exc)
        _audit("chat", outcome="failure", details={"error": str(exc)[:500]})
        # Broadcast error
        await broadcaster.broadcast("error", {
            "action": "chat",
            "error": str(exc)[:500],
        })
        # Check if it's an "all providers failed" error
        error_msg = str(exc)
        if "All LLM providers failed" in error_msg:
            raise HTTPException(status_code=502, detail="Les fournisseurs LLM sont indisponibles. Vérifiez vos clés API.")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# ═══════════════════════════════════════════════════════════════════
# 2. RUN TASK — POST /run
# ═══════════════════════════════════════════════════════════════════

@app.post("/run")
async def run_task(request: RunRequest):
    """
    Run a task through the NEXUS Plan-Execute-Reflect orchestrator.

    This is the primary endpoint for complex multi-step tasks.
    Broadcasts real-time events via the EventBroadcaster.
    """
    start = time.monotonic()
    broadcaster = _get_broadcaster()
    try:
        from nexus.orchestrator.langgraph_engine import run_nexus_task

        # Broadcast: task step starting
        await broadcaster.broadcast("task_step", {
            "task": request.task[:200],
            "step": "plan_execute_reflect",
            "provider": request.provider,
        })

        # Broadcast: agent thinking
        await broadcaster.broadcast("agent_thinking", {
            "task": request.task[:200],
            "phase": "planning",
        })

        try:
            result = await asyncio.wait_for(
                run_nexus_task(task=request.task, messages=[]),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Task execution timed out: %s", request.task[:100])
            raise HTTPException(status_code=504, detail="Task execution timed out after 120s")

        latency = (time.monotonic() - start) * 1000

        # Broadcast: task done
        await broadcaster.broadcast("task_done", {
            "task": request.task[:200],
            "status": result.get("status", "completed"),
            "steps": result.get("iterations", 0),
            "latency_ms": latency,
        })

        _audit("run_task", target=request.task[:100], details={"latency_ms": latency, "status": result.get("status")})

        return {
            "result": result.get("result", ""),
            "status": result.get("status", "completed"),
            "steps": result.get("iterations", 0),
            "plan": result.get("plan", ""),
            "reflection": result.get("reflection", ""),
            "thread_id": result.get("thread_id", ""),
            "latency_ms": latency,
        }

    except Exception as exc:
        logger.error("Task execution failed: %s", exc)
        _audit("run_task", target=request.task[:100], outcome="failure", details={"error": str(exc)[:500]})
        # Broadcast error
        await broadcaster.broadcast("error", {
            "action": "run_task",
            "task": request.task[:200],
            "error": str(exc)[:500],
        })
        raise HTTPException(status_code=500, detail="L'exécution de la tâche a échoué")


# ═══════════════════════════════════════════════════════════════════
# 3. MEMORY — GET /memory/stats, GET /memory/namespaces
# ═══════════════════════════════════════════════════════════════════

@app.get("/memory/stats")
async def get_memory_stats():
    """Get memory statistics across all namespaces."""
    try:
        service = _get_memory_service()
        namespaces = ["conversations", "episodes", "knowledge", "skills", "identity", "code"]
        stats = {}
        for ns in namespaces:
            try:
                count = await service.count(namespace=ns)
                stats[ns] = {"count": count}
            except Exception as exc:
                logger.warning("Namespace %s inaccessible: %s", ns, exc)
                stats[ns] = {"count": 0, "error": "namespace not accessible"}

        _audit("memory_stats", target="all")
        return {"namespaces": stats}
    except Exception as exc:
        logger.error("Memory stats failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not retrieve memory stats: {str(exc)}")


@app.get("/memory/namespaces")
async def get_memory_namespaces():
    """List all memory namespaces with their document counts."""
    try:
        service = _get_memory_service()
        namespaces = ["conversations", "episodes", "knowledge", "skills", "identity", "code"]
        result = {}
        for ns in namespaces:
            try:
                count = await service.count(namespace=ns)
                result[ns] = count
            except Exception as exc:
                logger.warning("Namespace %s inaccessible: %s", ns, exc)
                result[ns] = 0
        _audit("memory_namespaces", target="all")
        return result
    except Exception as exc:
        logger.error("Memory namespaces failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not list memory namespaces: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 3b. MEMORY LAYER ENDPOINTS — 5-Layer Memory API
# ═══════════════════════════════════════════════════════════════════

@app.post("/memory/recall")
async def memory_recall(request: Request):
    """Recall from all memory layers intelligently."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    query = body.get("query", "")
    n_results = body.get("n_results", 5)
    task_type = body.get("task_type", "general")
    user_id = body.get("user_id")
    session_id = body.get("session_id")

    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field")

    try:
        from nexus.memory.orchestrator import MemoryContext
        orchestrator = _get_memory_orchestrator()
        context = MemoryContext(
            task=query,
            task_type=task_type,
            user_id=user_id,
            session_id=session_id,
        )
        results = await orchestrator.recall(query=query, context=context, n_results=n_results)

        # Convert MemoryResult objects to dicts
        recall_data = []
        for r in results:
            recall_data.append({
                "memory_type": r.memory_type.value,
                "content": r.content if isinstance(r.content, str) else str(r.content),
                "relevance_score": r.relevance_score,
                "timestamp": r.timestamp,
                "metadata": r.metadata,
            })

        await broadcaster.broadcast("agent_action", {
            "action": "memory_recall",
            "query": query[:200],
            "results_count": len(recall_data),
        })

        _audit("memory_recall", target=query[:100], details={"results": len(recall_data)})

        return {
            "query": query,
            "results": recall_data,
            "count": len(recall_data),
        }

    except Exception as exc:
        logger.error("Memory recall failed: %s", exc)
        _audit("memory_recall", target=query[:100], outcome="failure", details={"error": str(exc)[:500]})
        await broadcaster.broadcast("error", {
            "action": "memory_recall",
            "error": str(exc)[:500],
        })
        raise HTTPException(status_code=500, detail=f"Memory recall failed: {str(exc)}")


@app.post("/memory/store")
async def memory_store(request: Request):
    """Store to appropriate memory layer."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    content = body.get("content", "")
    memory_type = body.get("type", "auto")  # auto, working, episodic, semantic, procedural, identity
    task_type = body.get("task_type", "general")
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    priority = body.get("priority", 1.0)
    metadata = body.get("metadata", {})

    if not content:
        raise HTTPException(status_code=400, detail="Missing 'content' field")

    try:
        if memory_type == "auto":
            # Use the orchestrator for auto-routing
            from nexus.memory.orchestrator import MemoryContext
            orchestrator = _get_memory_orchestrator()
            context = MemoryContext(
                task=content[:200],
                task_type=task_type,
                user_id=user_id,
                session_id=session_id,
                priority=priority,
                metadata=metadata,
            )
            storage_id = await orchestrator.store(data=content, context=context)
            result = {"storage_id": storage_id, "type": "auto_routed"}
        elif memory_type == "working":
            from nexus.memory.working import WorkingMemory, MessageRole
            wm = WorkingMemory()
            role_str = metadata.get("role", "assistant").upper()
            role = MessageRole(role_str) if role_str in ("SYSTEM", "USER", "ASSISTANT", "TOOL") else MessageRole.ASSISTANT
            wm.add(role=role, content=content, priority=priority)
            result = {"storage_id": f"working_{wm.total_tokens}", "type": "working"}
        elif memory_type == "episodic":
            from nexus.memory.episodic import Episode
            episodic = _get_episodic_memory()
            episode = Episode(
                task=content[:200],
                actions=metadata.get("actions", []),
                outcome=metadata.get("outcome", ""),
                success=metadata.get("success", True),
                tools_used=metadata.get("tools_used", []),
                tags=metadata.get("tags", []),
            )
            doc_id = await episodic.record(episode)
            result = {"storage_id": doc_id, "type": "episodic"}
        elif memory_type == "semantic":
            semantic = _get_semantic_memory()
            doc_id = await semantic.add_fact(
                text=content,
                source=metadata.get("source", "user"),
                confidence=metadata.get("confidence", 1.0),
                tags=metadata.get("tags"),
            )
            result = {"storage_id": doc_id, "type": "semantic"}
        elif memory_type == "procedural":
            from nexus.memory.procedural import Skill
            procedural = _get_procedural_memory()
            skill = Skill(
                name=metadata.get("name", content[:50]),
                description=content[:200],
                pattern=metadata.get("pattern", ""),
                steps=metadata.get("steps", []),
                success_criteria=metadata.get("success_criteria", ""),
                domain=metadata.get("domain", "general"),
                tags=metadata.get("tags", []),
            )
            doc_id = await procedural.crystallize(skill)
            result = {"storage_id": doc_id, "type": "procedural"}
        elif memory_type == "identity":
            from nexus.memory.identity import UserProfile
            identity = _get_identity_memory()
            profile = UserProfile(
                user_id=user_id or "default",
                display_name=metadata.get("display_name", ""),
                language_preference=metadata.get("language_preference"),
                communication_style=metadata.get("communication_style", "professional"),
                domain_expertise=metadata.get("domain_expertise", []),
                goals=metadata.get("goals", []),
                preferences=metadata.get("preferences", {}),
            )
            doc_id = await identity.create_or_update_profile(profile)
            result = {"storage_id": doc_id, "type": "identity"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown memory type: {memory_type}")

        await broadcaster.broadcast("agent_action", {
            "action": "memory_store",
            "memory_type": memory_type,
            "content_length": len(content),
        })

        _audit("memory_store", target=memory_type, details={"content_length": len(content)})

        return {"status": "stored", **result}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory store failed: %s", exc)
        _audit("memory_store", target=memory_type, outcome="failure", details={"error": str(exc)[:500]})
        await broadcaster.broadcast("error", {
            "action": "memory_store",
            "error": str(exc)[:500],
        })
        raise HTTPException(status_code=500, detail=f"Memory store failed: {str(exc)}")


@app.post("/memory/episodic/record")
async def episodic_record(request: Request):
    """Record an episode/experience."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        from nexus.memory.episodic import Episode
        episodic = _get_episodic_memory()
        episode = Episode(
            task=body.get("task", ""),
            actions=body.get("actions", []),
            outcome=body.get("outcome", ""),
            success=body.get("success", True),
            duration_seconds=body.get("duration_seconds", 0.0),
            tools_used=body.get("tools_used", []),
            model_used=body.get("model_used", ""),
            token_cost=body.get("token_cost", 0.0),
            tags=body.get("tags", []),
        )
        doc_id = await episodic.record(episode)

        await broadcaster.broadcast("agent_action", {
            "action": "episodic_record",
            "task": episode.task[:200],
            "success": episode.success,
        })

        _audit("episodic_record", target=episode.task[:100], details={"success": episode.success})

        return {"doc_id": doc_id, "task": episode.task, "success": episode.success, "status": "recorded"}

    except Exception as exc:
        logger.error("Episodic record failed: %s", exc)
        _audit("episodic_record", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Episodic record failed: {str(exc)}")


@app.post("/memory/episodic/recall")
async def episodic_recall(request: Request):
    """Recall similar past experiences."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    query = body.get("query", "")
    top_k = body.get("top_k", 5)

    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field")

    try:
        episodic = _get_episodic_memory()
        results = await episodic.recall_similar(query=query, top_k=top_k)

        await broadcaster.broadcast("agent_action", {
            "action": "episodic_recall",
            "query": query[:200],
            "results_count": len(results),
        })

        _audit("episodic_recall", target=query[:100], details={"results": len(results)})

        return {"query": query, "results": results, "count": len(results)}

    except Exception as exc:
        logger.error("Episodic recall failed: %s", exc)
        _audit("episodic_recall", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Episodic recall failed: {str(exc)}")


@app.post("/memory/semantic/add_fact")
async def semantic_add_fact(request: Request):
    """Add a knowledge fact."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' field")

    try:
        semantic = _get_semantic_memory()
        doc_id = await semantic.add_fact(
            text=text,
            source=body.get("source", "user"),
            confidence=body.get("confidence", 1.0),
            tags=body.get("tags"),
            fact_id=body.get("fact_id"),
        )

        await broadcaster.broadcast("agent_action", {
            "action": "semantic_add_fact",
            "fact_id": doc_id,
        })

        _audit("semantic_add_fact", target=text[:100], details={"doc_id": doc_id})

        return {"doc_id": doc_id, "text": text[:200], "status": "added"}

    except Exception as exc:
        logger.error("Semantic add fact failed: %s", exc)
        _audit("semantic_add_fact", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Semantic add fact failed: {str(exc)}")


@app.post("/memory/semantic/query")
async def semantic_query(request: Request):
    """Query semantic memory."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field")

    try:
        semantic = _get_semantic_memory()
        results = await semantic.query(
            query=query,
            top_k=body.get("top_k", 5),
            source_filter=body.get("source_filter"),
            min_confidence=body.get("min_confidence", 0.0),
        )

        await broadcaster.broadcast("agent_action", {
            "action": "semantic_query",
            "query": query[:200],
            "results_count": len(results),
        })

        _audit("semantic_query", target=query[:100], details={"results": len(results)})

        return {"query": query, "results": results, "count": len(results)}

    except Exception as exc:
        logger.error("Semantic query failed: %s", exc)
        _audit("semantic_query", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Semantic query failed: {str(exc)}")


@app.post("/memory/procedural/crystallize")
async def procedural_crystallize(request: Request):
    """Crystallize a skill from repeated successful patterns."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")

    try:
        from nexus.memory.procedural import Skill
        procedural = _get_procedural_memory()
        skill = Skill(
            name=name,
            description=body.get("description", ""),
            pattern=body.get("pattern", ""),
            steps=body.get("steps", []),
            success_criteria=body.get("success_criteria", ""),
            domain=body.get("domain", "general"),
            tags=body.get("tags", []),
        )
        doc_id = await procedural.crystallize(skill)

        await broadcaster.broadcast("agent_action", {
            "action": "procedural_crystallize",
            "skill_name": name,
            "doc_id": doc_id,
        })

        _audit("procedural_crystallize", target=name, details={"doc_id": doc_id})

        return {"doc_id": doc_id, "skill_name": name, "status": "crystallized"}

    except Exception as exc:
        logger.error("Procedural crystallize failed: %s", exc)
        _audit("procedural_crystallize", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Procedural crystallize failed: {str(exc)}")


@app.post("/memory/procedural/find_relevant")
async def procedural_find_relevant(request: Request):
    """Find relevant crystallized skills for a task."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    task_description = body.get("task_description", "")
    if not task_description:
        raise HTTPException(status_code=400, detail="Missing 'task_description' field")

    try:
        procedural = _get_procedural_memory()
        skills = await procedural.find_relevant(
            task_description=task_description,
            top_k=body.get("top_k", 3),
            min_quality=body.get("min_quality", 0.3),
        )

        await broadcaster.broadcast("agent_action", {
            "action": "procedural_find_relevant",
            "task_description": task_description[:200],
            "results_count": len(skills),
        })

        _audit("procedural_find_relevant", target=task_description[:100], details={"results": len(skills)})

        return {"task_description": task_description, "skills": skills, "count": len(skills)}

    except Exception as exc:
        logger.error("Procedural find relevant failed: %s", exc)
        _audit("procedural_find_relevant", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Procedural find relevant failed: {str(exc)}")


@app.post("/memory/identity/update")
async def identity_update(request: Request):
    """Update user identity/preferences."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    user_id = body.get("user_id", "default")

    try:
        from nexus.memory.identity import UserProfile
        identity = _get_identity_memory()
        profile = UserProfile(
            user_id=user_id,
            display_name=body.get("display_name", ""),
            language_preference=body.get("language_preference"),
            communication_style=body.get("communication_style", "professional"),
            domain_expertise=body.get("domain_expertise", []),
            goals=body.get("goals", []),
            preferences=body.get("preferences", {}),
        )
        doc_id = await identity.create_or_update_profile(profile)

        # Also record individual preferences if provided
        prefs = body.get("preferences", {})
        for key, value in prefs.items():
            try:
                await identity.record_preference(user_id, key, str(value))
            except Exception:
                pass

        await broadcaster.broadcast("agent_action", {
            "action": "identity_update",
            "user_id": user_id,
        })

        _audit("identity_update", target=user_id, details={"doc_id": doc_id})

        return {"doc_id": doc_id, "user_id": user_id, "status": "updated"}

    except Exception as exc:
        logger.error("Identity update failed: %s", exc)
        _audit("identity_update", target=user_id, outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Identity update failed: {str(exc)}")


@app.get("/memory/identity/profile")
async def identity_profile(
    user_id: str = Query("default", description="User identifier"),
):
    """Get current user identity profile."""
    try:
        identity = _get_identity_memory()
        profile = await identity.get_profile(user_id)

        _audit("identity_profile", target=user_id)

        if profile is None:
            return {"user_id": user_id, "profile": None, "status": "not_found"}
        return {"user_id": user_id, "profile": profile, "status": "found"}

    except Exception as exc:
        logger.error("Identity profile failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Identity profile failed: {str(exc)}")


@app.post("/memory/compact")
async def memory_compact():
    """Run memory compaction/maintenance."""
    broadcaster = _get_broadcaster()
    try:
        compactor = _get_memory_compactor()
        results = await compactor.run_maintenance()

        await broadcaster.broadcast("agent_action", {
            "action": "memory_compact",
            "namespaces_processed": len(results),
        })

        _audit("memory_compact", target="all", details={"namespaces": len(results)})

        return {"status": "completed", "results": results}

    except Exception as exc:
        logger.error("Memory compact failed: %s", exc)
        _audit("memory_compact", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Memory compact failed: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 3c. CAPABILITIES & SKILLS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/capabilities")
async def get_capabilities():
    """Get full list of agent capabilities — tools, skills, memory layers, agents, providers."""
    try:
        # Tools
        tool_names = sorted(TOOL_HANDLERS.keys())

        # Memory layers
        memory_layers = ["working", "episodic", "semantic", "procedural", "identity"]

        # Memory stats
        try:
            service = _get_memory_service()
            memory_stats = {}
            for ns in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
                try:
                    count = await service.count(namespace=ns)
                    memory_stats[ns] = count
                except Exception:
                    memory_stats[ns] = 0
        except Exception:
            memory_stats = {}

        # Agent types
        try:
            from nexus.core.registry import get_registry
            registry = get_registry()
            agent_types = registry.list_types()
        except Exception:
            agent_types = []

        # Providers
        try:
            router = _get_router()
            provider_status = router.get_provider_status()
        except Exception:
            provider_status = {}

        # Skills from procedural memory
        try:
            lifecycle = _get_skill_lifecycle()
            skills = lifecycle.list_skills()
        except Exception:
            skills = []

        _audit("get_capabilities")

        return {
            "tools": tool_names,
            "tool_count": len(tool_names),
            "memory_layers": memory_layers,
            "memory_stats": memory_stats,
            "agent_types": agent_types,
            "providers": provider_status,
            "skills": skills,
            "skill_count": len(skills),
        }

    except Exception as exc:
        logger.error("Get capabilities failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Get capabilities failed: {str(exc)}")


@app.get("/skills")
async def list_skills():
    """List all crystallized skills."""
    broadcaster = _get_broadcaster()
    try:
        lifecycle = _get_skill_lifecycle()
        skills = lifecycle.list_skills()

        # Also try to get skills from procedural memory
        try:
            service = _get_memory_service()
            count = await service.count(namespace="skills")
        except Exception:
            count = 0

        await broadcaster.broadcast("agent_action", {
            "action": "list_skills",
            "count": len(skills),
        })

        _audit("list_skills", details={"count": len(skills)})

        return {
            "skills": skills,
            "lifecycle_count": len(skills),
            "procedural_count": count,
        }

    except Exception as exc:
        logger.error("List skills failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"List skills failed: {str(exc)}")


@app.post("/skills/crystallize")
async def crystallize_skill(request: Request):
    """Manually trigger skill crystallization."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    task_pattern = body.get("task_pattern", "")
    if not task_pattern:
        raise HTTPException(status_code=400, detail="Missing 'task_pattern' field")

    try:
        lifecycle = _get_skill_lifecycle()
        skill = await lifecycle.discover_skill(
            task_pattern=task_pattern,
            frequency=body.get("frequency", 3),
            category=body.get("category", "general"),
        )

        await broadcaster.broadcast("agent_action", {
            "action": "skill_crystallize",
            "skill_name": skill.name,
            "skill_id": skill.skill_id,
            "stage": skill.stage.value,
        })

        _audit("skill_crystallize", target=task_pattern[:100], details={
            "skill_id": skill.skill_id,
            "stage": skill.stage.value,
        })

        return skill.to_dict()

    except Exception as exc:
        logger.error("Skill crystallize failed: %s", exc)
        _audit("skill_crystallize", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Skill crystallize failed: {str(exc)}")


@app.post("/skills/execute")
async def execute_skill(request: Request):
    """Execute a crystallized skill by name."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    skill_name = body.get("skill_name", "")
    if not skill_name:
        raise HTTPException(status_code=400, detail="Missing 'skill_name' field")

    try:
        # Try to find the skill in the lifecycle manager first
        lifecycle = _get_skill_lifecycle()
        all_skills = lifecycle.list_skills()
        matching = [s for s in all_skills if s.get("name") == skill_name]

        if matching:
            skill_def = matching[0]
            skill_id = skill_def.get("skill_id", "")
            skill_obj = lifecycle.get_skill(skill_id)

            if skill_obj and skill_obj.implementation:
                # Execute the skill's implementation via LLM
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()
                response = await router.complete(
                    messages=[
                        {"role": "system", "content": f"You are executing skill '{skill_name}'. {skill_obj.description}\n\nImplementation:\n{skill_obj.implementation[:2000]}"},
                        {"role": "user", "content": json.dumps(body.get("params", {}))},
                    ],
                    task_complexity=TaskComplexity.SIMPLE,
                    temperature=0.1,
                    max_tokens=2000,
                )
                result = response.content

                # Record usage
                try:
                    from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop
                    loop = SelfImprovementLoop()
                    await loop.record_usage(skill_id, success=True)
                except Exception:
                    pass
            else:
                result = f"Skill '{skill_name}' found but has no implementation yet (stage: {skill_def.get('stage', 'unknown')})"
        else:
            # Try procedural memory
            procedural = _get_procedural_memory()
            skill_data = await procedural.get_skill_by_name(skill_name)
            if skill_data:
                result = skill_data.get("text", f"Skill '{skill_name}' found in procedural memory")
            else:
                raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        await broadcaster.broadcast("agent_action", {
            "action": "skill_execute",
            "skill_name": skill_name,
        })

        _audit("skill_execute", target=skill_name)

        return {"skill_name": skill_name, "result": result, "status": "executed"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Skill execute failed: %s", exc)
        _audit("skill_execute", target=skill_name, outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Skill execute failed: {str(exc)}")


@app.post("/crons/schedule")
async def schedule_cron(request: Request):
    """Schedule a recurring task."""
    broadcaster = _get_broadcaster()
    try:
        body = await request.json()
    except Exception:
        body = {}

    task = body.get("task", "")
    interval_seconds = body.get("interval_seconds", 3600)
    agent_type = body.get("agent_type", "general")

    if not task:
        raise HTTPException(status_code=400, detail="Missing 'task' field")

    cron_id = uuid.uuid4().hex[:12]

    cron_entry = {
        "cron_id": cron_id,
        "task": task,
        "interval_seconds": interval_seconds,
        "agent_type": agent_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "run_count": 0,
        "status": "scheduled",
        "metadata": body.get("metadata", {}),
    }

    _scheduled_crons[cron_id] = cron_entry

    # Start the cron job in the background
    async def _run_cron():
        """Background task that runs on schedule."""
        entry = _scheduled_crons.get(cron_id)
        if not entry:
            return
        while entry.get("status") == "scheduled":
            await asyncio.sleep(interval_seconds)
            entry = _scheduled_crons.get(cron_id)
            if not entry or entry.get("status") != "scheduled":
                break
            try:
                entry["last_run"] = datetime.now(timezone.utc).isoformat()
                entry["run_count"] = entry.get("run_count", 0) + 1
                await broadcaster.broadcast("cron_run", {
                    "cron_id": cron_id,
                    "task": task[:200],
                    "run_count": entry["run_count"],
                })
                _audit("cron_run", target=cron_id, details={"task": task[:100], "run": entry["run_count"]})
            except Exception as exc:
                logger.error("Cron %s run failed: %s", cron_id, exc)

    # Fire and forget — don't await
    asyncio.create_task(_run_cron())

    await broadcaster.broadcast("agent_action", {
        "action": "cron_schedule",
        "cron_id": cron_id,
        "task": task[:200],
    })

    _audit("cron_schedule", target=cron_id, details={"task": task[:100], "interval": interval_seconds})

    return cron_entry


@app.get("/crons/list")
async def list_crons():
    """List scheduled tasks."""
    try:
        _audit("cron_list")
        return {
            "crons": list(_scheduled_crons.values()),
            "count": len(_scheduled_crons),
        }
    except Exception as exc:
        logger.error("List crons failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"List crons failed: {str(exc)}")


@app.delete("/crons/{cron_id}")
async def delete_cron(cron_id: str):
    """Cancel a scheduled task."""
    broadcaster = _get_broadcaster()
    if cron_id not in _scheduled_crons:
        raise HTTPException(status_code=404, detail=f"Cron '{cron_id}' not found")

    _scheduled_crons[cron_id]["status"] = "cancelled"
    entry = _scheduled_crons.pop(cron_id)

    await broadcaster.broadcast("agent_action", {
        "action": "cron_delete",
        "cron_id": cron_id,
    })

    _audit("cron_delete", target=cron_id)

    return {"cron_id": cron_id, "status": "cancelled", "previous_runs": entry.get("run_count", 0)}


# ═══════════════════════════════════════════════════════════════════
# 4. TOOLS — POST /tools/{tool_name}, GET /tools/search_memory
# ═══════════════════════════════════════════════════════════════════

# Map of tool_name → (handler_function, is_post)
# GET tools receive query params; POST tools receive a JSON body

async def _tool_search_memory(query: str = "", namespace: str = "knowledge", top_k: int = 5, **kwargs) -> Any:
    """Search vector memory for relevant documents."""
    service = _get_memory_service()
    results = await service.search(query=query, namespace=namespace, top_k=top_k)
    output = []
    ids = results.get("ids", [[]])[0] if results.get("ids") else []
    docs = (results.get("documents") or [[]])[0] if results.get("documents") else []
    metas = (results.get("metadatas") or [[]])[0] if results.get("metadatas") else []
    dists = (results.get("distances") or [[]])[0] if results.get("distances") else []
    for i, doc_id in enumerate(ids):
        output.append({
            "id": doc_id,
            "text": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {},
            "distance": dists[i] if i < len(dists) else 0.0,
        })
    return output


async def _tool_store_memory(text: str = "", namespace: str = "knowledge", source: str = "user", **kwargs) -> Any:
    """Store a document in vector memory."""
    service = _get_memory_service()
    metadata = {"source": source}
    doc_id = await service.store(text=text, metadata=metadata, namespace=namespace)
    return {"doc_id": doc_id, "namespace": namespace, "status": "stored"}


async def _tool_delete_memory(doc_id: str = "", namespace: str = "knowledge", **kwargs) -> Any:
    """Delete a document from vector memory."""
    service = _get_memory_service()
    await service.delete(doc_id=doc_id, namespace=namespace)
    return {"doc_id": doc_id, "namespace": namespace, "status": "deleted"}


async def _tool_knowledge_query(entity_name: str = "", depth: int = 1, **kwargs) -> Any:
    """Query the Knowledge Graph for an entity and its relationships."""
    kg = _get_knowledge_graph()
    entity = kg.get_entity(entity_name)
    if not entity:
        return {"error": f"Entity '{entity_name}' not found"}
    rels = kg.get_relationships(entity_name)
    neighbors = kg.get_neighbors(entity_name, degree=depth)
    return {"entity": entity, "relationships": rels, "neighbors": neighbors}


async def _tool_knowledge_add_entity(name: str = "", entity_type: str = "concept", **kwargs) -> Any:
    """Add an entity to the Knowledge Graph."""
    kg = _get_knowledge_graph()
    node_id = kg.add_entity(name, entity_type=entity_type)
    return {"node_id": node_id, "name": name, "entity_type": entity_type, "status": "added"}


async def _tool_knowledge_search(query: str = "", entity_type: Optional[str] = None, limit: int = 20, **kwargs) -> Any:
    """Search entities in the Knowledge Graph by name."""
    kg = _get_knowledge_graph()
    return kg.search_entities(query, entity_type=entity_type, limit=limit)


async def _tool_knowledge_paths(source_name: str = "", target_name: str = "", max_length: int = 5, **kwargs) -> Any:
    """Find paths between two entities in the Knowledge Graph."""
    kg = _get_knowledge_graph()
    paths = kg.find_paths(source_name, target_name, max_length=max_length)
    return {"paths": paths}


async def _tool_knowledge_add_relation(source_name: str = "", target_name: str = "", relation_type: str = "", **kwargs) -> Any:
    """Add a relationship between two entities."""
    kg = _get_knowledge_graph()
    kg.add_relationship(source_name, target_name, relation_type)
    return {"source": source_name, "target": target_name, "relation": relation_type, "status": "added"}


async def _tool_spawn_agent(task: str = "", agent_type: str = "general", **kwargs) -> Any:
    """Spawn a sub-agent to handle a specific task."""
    from nexus.core.registry import get_registry
    registry = get_registry()
    instance = registry.spawn(agent_type, task=task)
    return {
        "status": "spawned",
        "instance_id": instance.instance_id,
        "agent_type": agent_type,
        "task": task[:200],
    }


async def _tool_list_agents(**kwargs) -> Any:
    """List all registered agent types and their instances."""
    from nexus.core.registry import get_registry
    registry = get_registry()
    return {
        "types": registry.list_types(),
        "stats": registry.get_stats(),
    }


async def _tool_execute_code(code: str = "", language: str = "python", timeout: int = 30, **kwargs) -> Any:
    """Execute code in a local subprocess."""
    from nexus.dev.code_executor import CodeExecutor
    executor = CodeExecutor(backend="local", timeout=timeout)
    result = await executor.execute(code, language=language, timeout=timeout)
    return {
        "stdout": result.stdout[:5000],
        "stderr": result.stderr[:5000],
        "exit_code": result.exit_code,
        "language": result.language,
        "timed_out": result.timed_out,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_execute_sandboxed(code: str = "", timeout: int = 30, max_memory_mb: int = 512, **kwargs) -> Any:
    """Execute Python code in a strict sandbox with resource limits."""
    from nexus.security.sandbox import LocalSandbox
    sandbox = LocalSandbox(timeout=timeout, max_memory_mb=max_memory_mb)
    result = await sandbox.execute_python(code, timeout=timeout)
    return {
        "stdout": result.stdout[:5000],
        "stderr": result.stderr[:5000],
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_install_package(package: str = "", version: Optional[str] = None, **kwargs) -> Any:
    """Install a Python package using pip."""
    import asyncio
    spec = f"{package}=={version}" if version else package
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", spec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return {
            "package": package,
            "version": version,
            "exit_code": proc.returncode,
            "output": (stdout or b"")[-2000:].decode(errors="replace"),
            "error": (stderr or b"")[-1000:].decode(errors="replace"),
        }
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"package": package, "exit_code": -1, "error": "Package installation timed out"}


def _validate_path(path: str, working_dir: Optional[Path] = None) -> Path | None:
    """Validate and resolve a path, checking it's within the working directory."""
    working = working_dir or _get_working_dir()
    safe = _safe_path(path, working)
    if safe is None:
        return None
    return safe


async def _tool_read_file(path: str = "", encoding: str = "utf-8", **kwargs) -> Any:
    """Read a file from the filesystem."""
    safe = _validate_path(path)
    if safe is None:
        return {"error": f"Access denied: path outside working directory"}
    if not safe.exists():
        return {"error": f"File not found: {path}"}
    if not safe.is_file():
        return {"error": f"Not a file: {path}"}
    content = safe.read_text(encoding=encoding)
    return {"path": str(safe), "size_bytes": safe.stat().st_size, "content": content[:50000]}


async def _tool_write_file(path: str = "", content: str = "", encoding: str = "utf-8", **kwargs) -> Any:
    """Write content to a file."""
    safe = _validate_path(path)
    if safe is None:
        return {"error": f"Access denied: path outside working directory"}
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(content, encoding=encoding)
    return {"path": str(safe), "bytes_written": len(content.encode(encoding)), "status": "written"}


async def _tool_list_files(directory: str = ".", pattern: str = "*", **kwargs) -> Any:
    """List files in a directory."""
    safe = _validate_path(directory)
    if safe is None:
        return {"error": f"Access denied: path outside working directory"}
    if not safe.exists():
        return {"error": f"Directory not found: {directory}"}
    files = []
    for p in safe.glob(pattern):
        try:
            files.append({
                "name": p.name,
                "path": str(p),
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
            })
        except OSError:
            continue
    return {"directory": str(safe), "pattern": pattern, "count": len(files), "files": files[:200]}


async def _tool_delete_file(path: str = "", **kwargs) -> Any:
    """Delete a file from the filesystem."""
    safe = _validate_path(path)
    if safe is None:
        return {"error": f"Access denied: path outside working directory"}
    if not safe.exists():
        return {"error": f"File not found: {path}"}
    if safe.is_dir():
        return {"error": f"Path is a directory, not a file: {path}"}
    safe.unlink()
    return {"path": str(safe), "status": "deleted"}


async def _tool_move_file(source: str = "", destination: str = "", **kwargs) -> Any:
    """Move a file from source to destination."""
    import shutil
    src_safe = _validate_path(source)
    dst_safe = _validate_path(destination)
    if src_safe is None or dst_safe is None:
        return {"error": f"Access denied: path outside working directory"}
    if not src_safe.exists():
        return {"error": f"Source not found: {source}"}
    dst_safe.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_safe), str(dst_safe))
    return {"source": source, "destination": destination, "status": "moved"}


async def _tool_copy_file(source: str = "", destination: str = "", **kwargs) -> Any:
    """Copy a file from source to destination."""
    import shutil
    src_safe = _validate_path(source)
    dst_safe = _validate_path(destination)
    if src_safe is None or dst_safe is None:
        return {"error": f"Access denied: path outside working directory"}
    if not src_safe.exists():
        return {"error": f"Source not found: {source}"}
    dst_safe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_safe, dst_safe)
    return {"source": source, "destination": destination, "status": "copied"}


async def _tool_web_search(query: str = "", num_results: int = 5, **kwargs) -> Any:
    """Search the web for information."""
    from nexus.knowledge.web_search import MultiSourceWebSearch
    search = MultiSourceWebSearch()
    results = await search.search(query, num_results=num_results)
    output = [
        {"title": r.title, "url": r.url, "snippet": r.snippet, "engine": r.source_engine}
        for r in results
    ]
    return {"query": query, "results": output}


async def _tool_reason_react(task: str = "", max_iterations: int = 10, **kwargs) -> Any:
    """Solve a task using ReAct (Reason+Act) reasoning."""
    from nexus.reasoning.react import ReActLoop
    reasoner = ReActLoop(max_iterations=max_iterations)
    result = await reasoner.run(task, tools=kwargs.get("tools"))
    return {
        "answer": result.get("answer", ""),
        "iterations": result.get("steps", 0),
        "reasoning_trace": result.get("thoughts", []),
        "actions": result.get("actions", []),
        "observations": result.get("observations", []),
    }


async def _tool_reason_tot(task: str = "", max_depth: int = 3, branch_factor: int = 3, **kwargs) -> Any:
    """Solve a task using Tree-of-Thought reasoning."""
    from nexus.reasoning.tot import TreeOfThought
    tot = TreeOfThought(max_depth=max_depth, branch_factor=branch_factor)
    result = await tot.solve(task)
    return {
        "answer": result.answer,
        "best_path": result.best_path,
        "total_nodes_explored": result.total_nodes_explored,
        "max_depth_reached": result.max_depth_reached,
    }


async def _tool_run_pipeline(main_task: str = "", sub_tasks_json: str = "[]", stages_json: str = "[]", **kwargs) -> Any:
    """Execute a pipeline pattern (sequential chain of agents)."""
    from nexus.orchestrator.patterns import pipeline_pattern
    stages = json.loads(stages_json) if stages_json != "[]" else [{"agent": "general", "description": main_task}]
    result = await pipeline_pattern(main_task=main_task, stages=stages)
    return {
        "pattern": "pipeline",
        "success": result.success,
        "total_tasks": result.total_tasks,
        "completed_tasks": result.completed_tasks,
        "results": result.results,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_run_parallel(main_task: str = "", sub_tasks_json: str = "[]", **kwargs) -> Any:
    """Execute a parallel pattern (multiple agents work simultaneously)."""
    from nexus.orchestrator.patterns import parallel_pattern
    sub_tasks = json.loads(sub_tasks_json)
    result = await parallel_pattern(main_task=main_task, sub_tasks=sub_tasks)
    return {
        "pattern": "parallel",
        "success": result.success,
        "total_tasks": result.total_tasks,
        "completed_tasks": result.completed_tasks,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_run_supervisor(main_task: str = "", sub_tasks_json: str = "[]", **kwargs) -> Any:
    """Execute a supervisor pattern (central agent delegates to workers)."""
    from nexus.orchestrator.patterns import supervisor_pattern
    sub_tasks = json.loads(sub_tasks_json)
    result = await supervisor_pattern(main_task=main_task, sub_tasks=sub_tasks)
    return {
        "pattern": "supervisor",
        "success": result.success,
        "total_tasks": result.total_tasks,
        "completed_tasks": result.completed_tasks,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_run_swarm(main_task: str = "", num_agents: int = 3, iterations: int = 2, **kwargs) -> Any:
    """Execute a swarm pattern (self-organizing agent collective)."""
    from nexus.orchestrator.patterns import swarm_pattern
    result = await swarm_pattern(main_task=main_task, num_agents=num_agents, iterations=iterations)
    return {
        "pattern": "swarm",
        "success": result.success,
        "total_tasks": result.total_tasks,
        "completed_tasks": result.completed_tasks,
        "execution_time_ms": result.execution_time_ms,
    }


async def _tool_audit_query(limit: int = 50, **kwargs) -> Any:
    """Query the audit log."""
    audit = _get_audit_logger()
    entries = audit.query(limit=limit)
    return {"entries": entries, "count": len(entries)}


async def _tool_get_status(**kwargs) -> Any:
    """Get comprehensive NEXUS agent status."""
    from nexus.core.config import get_settings
    settings = get_settings()
    return {
        "agent": "NEXUS",
        "version": "0.1.0",
        "status": "running",
        "environment": settings.nexus_env.value,
        "providers_configured": settings.available_providers,
    }


# ── Memory Layer Tool Handlers ────────────────────────────────────

async def _tool_memory_recall(query: str = "", n_results: int = 5, task_type: str = "general",
                               user_id: str = "", session_id: str = "", **kwargs) -> Any:
    """Recall from all memory layers intelligently."""
    if not query:
        return {"error": "Missing 'query' parameter"}
    try:
        from nexus.memory.orchestrator import MemoryContext
        orchestrator = _get_memory_orchestrator()
        context = MemoryContext(task=query, task_type=task_type,
                                user_id=user_id or None, session_id=session_id or None)
        results = await orchestrator.recall(query=query, context=context, n_results=n_results)
        recall_data = []
        for r in results:
            recall_data.append({
                "memory_type": r.memory_type.value,
                "content": r.content if isinstance(r.content, str) else str(r.content),
                "relevance_score": r.relevance_score,
                "timestamp": r.timestamp,
                "metadata": r.metadata,
            })
        return {"query": query, "results": recall_data, "count": len(recall_data)}
    except Exception as exc:
        logger.error("Tool memory_recall failed: %s", exc)
        return {"error": str(exc)}


async def _tool_memory_store(content: str = "", type: str = "auto", task_type: str = "general",
                              user_id: str = "", session_id: str = "", priority: float = 1.0,
                              metadata: Optional[dict] = None, **kwargs) -> Any:
    """Store to appropriate memory layer."""
    if not content:
        return {"error": "Missing 'content' parameter"}
    try:
        if type == "auto":
            from nexus.memory.orchestrator import MemoryContext
            orchestrator = _get_memory_orchestrator()
            context = MemoryContext(task=content[:200], task_type=task_type,
                                    user_id=user_id or None, session_id=session_id or None,
                                    priority=priority, metadata=metadata or {})
            storage_id = await orchestrator.store(data=content, context=context)
            return {"storage_id": storage_id, "type": "auto_routed", "status": "stored"}
        elif type == "episodic":
            from nexus.memory.episodic import Episode
            episodic = _get_episodic_memory()
            meta = metadata or {}
            episode = Episode(task=content[:200], actions=meta.get("actions", []),
                              outcome=meta.get("outcome", ""), success=meta.get("success", True),
                              tools_used=meta.get("tools_used", []), tags=meta.get("tags", []))
            doc_id = await episodic.record(episode)
            return {"storage_id": doc_id, "type": "episodic", "status": "stored"}
        elif type == "semantic":
            semantic = _get_semantic_memory()
            meta = metadata or {}
            doc_id = await semantic.add_fact(text=content, source=meta.get("source", "user"),
                                              confidence=meta.get("confidence", 1.0), tags=meta.get("tags"))
            return {"storage_id": doc_id, "type": "semantic", "status": "stored"}
        elif type == "procedural":
            from nexus.memory.procedural import Skill
            procedural = _get_procedural_memory()
            meta = metadata or {}
            skill = Skill(name=meta.get("name", content[:50]), description=content[:200],
                          pattern=meta.get("pattern", ""), steps=meta.get("steps", []),
                          success_criteria=meta.get("success_criteria", ""), domain=meta.get("domain", "general"),
                          tags=meta.get("tags", []))
            doc_id = await procedural.crystallize(skill)
            return {"storage_id": doc_id, "type": "procedural", "status": "stored"}
        elif type == "identity":
            from nexus.memory.identity import UserProfile
            identity = _get_identity_memory()
            meta = metadata or {}
            profile = UserProfile(user_id=user_id or "default", display_name=meta.get("display_name", ""),
                                   language_preference=meta.get("language_preference"),
                                   communication_style=meta.get("communication_style", "professional"),
                                   domain_expertise=meta.get("domain_expertise", []),
                                   goals=meta.get("goals", []), preferences=meta.get("preferences", {}))
            doc_id = await identity.create_or_update_profile(profile)
            return {"storage_id": doc_id, "type": "identity", "status": "stored"}
        else:
            return {"error": f"Unknown memory type: {type}"}
    except Exception as exc:
        logger.error("Tool memory_store failed: %s", exc)
        return {"error": str(exc)}


async def _tool_episodic_record(task: str = "", actions: str = "[]", outcome: str = "",
                                 success: bool = True, **kwargs) -> Any:
    """Record an episode/experience."""
    if not task:
        return {"error": "Missing 'task' parameter"}
    try:
        from nexus.memory.episodic import Episode
        episodic = _get_episodic_memory()
        action_list = json.loads(actions) if isinstance(actions, str) else actions
        episode = Episode(task=task, actions=action_list, outcome=outcome, success=success,
                          tools_used=kwargs.get("tools_used", []),
                          tags=kwargs.get("tags", []))
        doc_id = await episodic.record(episode)
        return {"doc_id": doc_id, "status": "recorded"}
    except Exception as exc:
        logger.error("Tool episodic_record failed: %s", exc)
        return {"error": str(exc)}


async def _tool_episodic_recall(query: str = "", top_k: int = 5, **kwargs) -> Any:
    """Recall similar past experiences."""
    if not query:
        return {"error": "Missing 'query' parameter"}
    try:
        episodic = _get_episodic_memory()
        results = await episodic.recall_similar(query=query, top_k=top_k)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as exc:
        logger.error("Tool episodic_recall failed: %s", exc)
        return {"error": str(exc)}


async def _tool_semantic_add_fact(text: str = "", source: str = "user",
                                   confidence: float = 1.0, tags: str = "", **kwargs) -> Any:
    """Add a knowledge fact."""
    if not text:
        return {"error": "Missing 'text' parameter"}
    try:
        semantic = _get_semantic_memory()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if isinstance(tags, str) else tags
        doc_id = await semantic.add_fact(text=text, source=source, confidence=confidence,
                                          tags=tag_list or None)
        return {"doc_id": doc_id, "status": "added"}
    except Exception as exc:
        logger.error("Tool semantic_add_fact failed: %s", exc)
        return {"error": str(exc)}


async def _tool_semantic_query(query: str = "", top_k: int = 5, **kwargs) -> Any:
    """Query semantic memory."""
    if not query:
        return {"error": "Missing 'query' parameter"}
    try:
        semantic = _get_semantic_memory()
        results = await semantic.query(query=query, top_k=top_k,
                                        source_filter=kwargs.get("source_filter"),
                                        min_confidence=kwargs.get("min_confidence", 0.0))
        return {"query": query, "results": results, "count": len(results)}
    except Exception as exc:
        logger.error("Tool semantic_query failed: %s", exc)
        return {"error": str(exc)}


async def _tool_procedural_crystallize(name: str = "", description: str = "", pattern: str = "",
                                        steps_json: str = "[]", success_criteria: str = "",
                                        domain: str = "general", **kwargs) -> Any:
    """Crystallize a skill from repeated successful patterns."""
    if not name:
        return {"error": "Missing 'name' parameter"}
    try:
        from nexus.memory.procedural import Skill
        procedural = _get_procedural_memory()
        steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
        skill = Skill(name=name, description=description, pattern=pattern, steps=steps,
                      success_criteria=success_criteria, domain=domain,
                      tags=kwargs.get("tags", []))
        doc_id = await procedural.crystallize(skill)
        return {"doc_id": doc_id, "skill_name": name, "status": "crystallized"}
    except Exception as exc:
        logger.error("Tool procedural_crystallize failed: %s", exc)
        return {"error": str(exc)}


async def _tool_procedural_find_relevant(task_description: str = "", top_k: int = 3, **kwargs) -> Any:
    """Find relevant crystallized skills for a task."""
    if not task_description:
        return {"error": "Missing 'task_description' parameter"}
    try:
        procedural = _get_procedural_memory()
        skills = await procedural.find_relevant(task_description=task_description, top_k=top_k,
                                                 min_quality=kwargs.get("min_quality", 0.3))
        return {"task_description": task_description, "skills": skills, "count": len(skills)}
    except Exception as exc:
        logger.error("Tool procedural_find_relevant failed: %s", exc)
        return {"error": str(exc)}


async def _tool_identity_update(user_id: str = "default", **kwargs) -> Any:
    """Update user identity/preferences."""
    try:
        from nexus.memory.identity import UserProfile
        identity = _get_identity_memory()
        profile = UserProfile(user_id=user_id, display_name=kwargs.get("display_name", ""),
                               language_preference=kwargs.get("language_preference"),
                               communication_style=kwargs.get("communication_style", "professional"),
                               domain_expertise=kwargs.get("domain_expertise", []),
                               goals=kwargs.get("goals", []), preferences=kwargs.get("preferences", {}))
        doc_id = await identity.create_or_update_profile(profile)
        return {"doc_id": doc_id, "user_id": user_id, "status": "updated"}
    except Exception as exc:
        logger.error("Tool identity_update failed: %s", exc)
        return {"error": str(exc)}


async def _tool_identity_profile(user_id: str = "default", **kwargs) -> Any:
    """Get current user identity profile."""
    try:
        identity = _get_identity_memory()
        profile = await identity.get_profile(user_id)
        if profile is None:
            return {"user_id": user_id, "profile": None, "status": "not_found"}
        return {"user_id": user_id, "profile": profile, "status": "found"}
    except Exception as exc:
        logger.error("Tool identity_profile failed: %s", exc)
        return {"error": str(exc)}


async def _tool_memory_compact(**kwargs) -> Any:
    """Run memory compaction/maintenance."""
    try:
        compactor = _get_memory_compactor()
        results = await compactor.run_maintenance()
        return {"status": "completed", "results": results}
    except Exception as exc:
        logger.error("Tool memory_compact failed: %s", exc)
        return {"error": str(exc)}


# ── Skill Tool Handlers ───────────────────────────────────────────

async def _tool_list_skills(**kwargs) -> Any:
    """List all crystallized skills."""
    try:
        lifecycle = _get_skill_lifecycle()
        skills = lifecycle.list_skills()
        return {"skills": skills, "count": len(skills)}
    except Exception as exc:
        logger.error("Tool list_skills failed: %s", exc)
        return {"error": str(exc)}


async def _tool_crystallize_skill(task_pattern: str = "", frequency: int = 3,
                                   category: str = "general", **kwargs) -> Any:
    """Manually trigger skill crystallization."""
    if not task_pattern:
        return {"error": "Missing 'task_pattern' parameter"}
    try:
        lifecycle = _get_skill_lifecycle()
        skill = await lifecycle.discover_skill(task_pattern=task_pattern, frequency=frequency,
                                                category=category)
        return skill.to_dict()
    except Exception as exc:
        logger.error("Tool crystallize_skill failed: %s", exc)
        return {"error": str(exc)}


async def _tool_execute_skill(skill_name: str = "", params: str = "{}", **kwargs) -> Any:
    """Execute a crystallized skill by name."""
    if not skill_name:
        return {"error": "Missing 'skill_name' parameter"}
    try:
        lifecycle = _get_skill_lifecycle()
        all_skills = lifecycle.list_skills()
        matching = [s for s in all_skills if s.get("name") == skill_name]
        if matching:
            skill_def = matching[0]
            skill_id = skill_def.get("skill_id", "")
            skill_obj = lifecycle.get_skill(skill_id)
            if skill_obj and skill_obj.implementation:
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()
                params_dict = json.loads(params) if isinstance(params, str) else params
                response = await router.complete(
                    messages=[
                        {"role": "system", "content": f"You are executing skill '{skill_name}'. {skill_obj.description}\n\nImplementation:\n{skill_obj.implementation[:2000]}"},
                        {"role": "user", "content": json.dumps(params_dict)},
                    ],
                    task_complexity=TaskComplexity.SIMPLE, temperature=0.1, max_tokens=2000,
                )
                return {"skill_name": skill_name, "result": response.content, "status": "executed"}
            else:
                return {"skill_name": skill_name, "result": f"Skill found but no implementation (stage: {skill_def.get('stage', 'unknown')})", "status": "no_implementation"}
        else:
            # Try procedural memory
            procedural = _get_procedural_memory()
            skill_data = await procedural.get_skill_by_name(skill_name)
            if skill_data:
                return {"skill_name": skill_name, "result": skill_data.get("text", ""), "status": "found_in_procedural"}
            return {"error": f"Skill '{skill_name}' not found"}
    except Exception as exc:
        logger.error("Tool execute_skill failed: %s", exc)
        return {"error": str(exc)}


# ── Cron Tool Handlers ────────────────────────────────────────────

async def _tool_schedule_cron(task: str = "", interval_seconds: int = 3600,
                               agent_type: str = "general", **kwargs) -> Any:
    """Schedule a recurring task."""
    if not task:
        return {"error": "Missing 'task' parameter"}
    try:
        cron_id = uuid.uuid4().hex[:12]
        cron_entry = {
            "cron_id": cron_id, "task": task, "interval_seconds": interval_seconds,
            "agent_type": agent_type, "created_at": datetime.now(timezone.utc).isoformat(),
            "last_run": None, "run_count": 0, "status": "scheduled",
            "metadata": kwargs.get("metadata", {}),
        }
        _scheduled_crons[cron_id] = cron_entry

        broadcaster = _get_broadcaster()

        async def _run_cron():
            entry = _scheduled_crons.get(cron_id)
            if not entry:
                return
            while entry.get("status") == "scheduled":
                await asyncio.sleep(interval_seconds)
                entry = _scheduled_crons.get(cron_id)
                if not entry or entry.get("status") != "scheduled":
                    break
                try:
                    entry["last_run"] = datetime.now(timezone.utc).isoformat()
                    entry["run_count"] = entry.get("run_count", 0) + 1
                    await broadcaster.broadcast("cron_run", {"cron_id": cron_id, "task": task[:200]})
                except Exception as exc:
                    logger.error("Cron %s run failed: %s", cron_id, exc)

        asyncio.create_task(_run_cron())
        return cron_entry
    except Exception as exc:
        logger.error("Tool schedule_cron failed: %s", exc)
        return {"error": str(exc)}


async def _tool_list_crons(**kwargs) -> Any:
    """List scheduled tasks."""
    return {"crons": list(_scheduled_crons.values()), "count": len(_scheduled_crons)}


# Tool dispatcher registry
TOOL_HANDLERS: dict[str, Any] = {
    "search_memory": _tool_search_memory,
    "store_memory": _tool_store_memory,
    "delete_memory": _tool_delete_memory,
    "knowledge_query": _tool_knowledge_query,
    "knowledge_add_entity": _tool_knowledge_add_entity,
    "knowledge_search": _tool_knowledge_search,
    "knowledge_paths": _tool_knowledge_paths,
    "knowledge_add_relation": _tool_knowledge_add_relation,
    "spawn_agent": _tool_spawn_agent,
    "list_agents": _tool_list_agents,
    "execute_code": _tool_execute_code,
    "execute_sandboxed": _tool_execute_sandboxed,
    "install_package": _tool_install_package,
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "list_files": _tool_list_files,
    "delete_file": _tool_delete_file,
    "move_file": _tool_move_file,
    "copy_file": _tool_copy_file,
    "web_search": _tool_web_search,
    "reason_react": _tool_reason_react,
    "reason_tot": _tool_reason_tot,
    "run_pipeline": _tool_run_pipeline,
    "run_parallel": _tool_run_parallel,
    "run_supervisor": _tool_run_supervisor,
    "run_swarm": _tool_run_swarm,
    "audit_query": _tool_audit_query,
    "get_status": _tool_get_status,
    # Memory layer tools
    "memory_recall": _tool_memory_recall,
    "memory_store": _tool_memory_store,
    "episodic_record": _tool_episodic_record,
    "episodic_recall": _tool_episodic_recall,
    "semantic_add_fact": _tool_semantic_add_fact,
    "semantic_query": _tool_semantic_query,
    "procedural_crystallize": _tool_procedural_crystallize,
    "procedural_find_relevant": _tool_procedural_find_relevant,
    "identity_update": _tool_identity_update,
    "identity_profile": _tool_identity_profile,
    "memory_compact": _tool_memory_compact,
    # Skill tools
    "list_skills": _tool_list_skills,
    "crystallize_skill": _tool_crystallize_skill,
    "execute_skill": _tool_execute_skill,
    # Cron tools
    "schedule_cron": _tool_schedule_cron,
    "list_crons": _tool_list_crons,
    # Avatar tools (lazy-imported)
}

def _lazy_avatar_handler(tool_name: str):
    """Return an async handler for an avatar tool."""
    async def handler(**kwargs: Any) -> Any:
        from nexus.mcp_tools.avatar_tools import (
            avatar_start, avatar_speak, avatar_set_vrm, avatar_set_expression,
            avatar_list_voices, avatar_set_speaker, avatar_start_conversation,
        )
        _TOOL_MAP = {
            "avatar_start": avatar_start,
            "avatar_speak": avatar_speak,
            "avatar_set_vrm": avatar_set_vrm,
            "avatar_set_expression": avatar_set_expression,
            "avatar_list_voices": avatar_list_voices,
            "avatar_set_speaker": avatar_set_speaker,
            "avatar_start_conversation": avatar_start_conversation,
        }
        fn = _TOOL_MAP[tool_name]
        return await fn(**kwargs)
    return handler

for _name in [
    "avatar_start", "avatar_speak", "avatar_set_vrm", "avatar_set_expression",
    "avatar_list_voices", "avatar_set_speaker", "avatar_start_conversation",
]:
    TOOL_HANDLERS[_name] = _lazy_avatar_handler(_name)


@app.post("/tools/{tool_name}")
async def execute_tool_post(tool_name: str, request: Request):
    """
    Generic tool execution endpoint — POST with JSON body.

    Dispatches to the appropriate MCP tool handler based on tool_name.
    The request body is passed as keyword arguments to the handler.
    """
    if tool_name not in TOOL_HANDLERS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool '{tool_name}'. Available tools: {sorted(TOOL_HANDLERS.keys())}",
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    handler = TOOL_HANDLERS[tool_name]

    try:
        result = await handler(**body)
        _audit(f"tool:{tool_name}", target=str(body)[:200])
        return result
    except TypeError as exc:
        # Likely a missing required parameter
        logger.warning("Tool %s called with invalid params: %s", tool_name, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{tool_name}' received invalid parameters: {str(exc)}",
        )
    except Exception as exc:
        logger.error("Tool '%s' execution failed: %s", tool_name, exc)
        _audit(f"tool:{tool_name}", target=str(body)[:200], outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {str(exc)}")


@app.get("/tools/search_memory")
async def search_memory_get(
    query: str = Query(..., description="Search query"),
    namespace: str = Query("knowledge", description="Memory namespace"),
    top_k: int = Query(10, ge=1, le=100, description="Number of results"),
):
    """Search vector memory (GET endpoint for convenience)."""
    try:
        result = await _tool_search_memory(query=query, namespace=namespace, top_k=top_k)
        _audit("tool:search_memory", target=query[:100])
        return result
    except Exception as exc:
        logger.error("Memory search failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(exc)}")


@app.get("/tools/{tool_name}")
async def execute_tool_get(tool_name: str, request: Request):
    """
    Generic tool GET endpoint — passes query params as kwargs.

    Supports tools like knowledge_query, knowledge_search, read_file, etc.
    """
    if tool_name not in TOOL_HANDLERS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool '{tool_name}'. Available tools: {sorted(TOOL_HANDLERS.keys())}",
        )

    # Convert query params to dict, parsing numbers and booleans
    params = dict(request.query_params)
    coerced = {}
    for k, v in params.items():
        # Try to parse as int
        try:
            coerced[k] = int(v)
            continue
        except (ValueError, TypeError):
            pass
        # Try to parse as float
        try:
            coerced[k] = float(v)
            continue
        except (ValueError, TypeError):
            pass
        # Try to parse as boolean
        if v.lower() in ("true", "1", "yes"):
            coerced[k] = True
            continue
        if v.lower() in ("false", "0", "no"):
            coerced[k] = False
            continue
        coerced[k] = v

    handler = TOOL_HANDLERS[tool_name]

    try:
        result = await handler(**coerced)
        _audit(f"tool:{tool_name}", target=str(coerced)[:200])
        return result
    except TypeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{tool_name}' received invalid parameters: {str(exc)}",
        )
    except Exception as exc:
        logger.error("Tool '%s' execution failed: %s", tool_name, exc)
        _audit(f"tool:{tool_name}", target=str(coerced)[:200], outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 5. KNOWLEDGE — GET /knowledge/query, GET /knowledge/search
# ═══════════════════════════════════════════════════════════════════

@app.get("/knowledge/query")
async def query_knowledge_graph(
    entity_name: str = Query(..., description="Entity name to query"),
    depth: int = Query(1, ge=1, le=5, description="Neighbor depth to explore"),
):
    """Query the Knowledge Graph for an entity and its relationships."""
    try:
        kg = _get_knowledge_graph()
        entity = kg.get_entity(entity_name)
        if not entity:
            return {"error": f"Entity '{entity_name}' not found", "entity": None, "relationships": [], "neighbors": []}
        rels = kg.get_relationships(entity_name)
        neighbors = kg.get_neighbors(entity_name, degree=depth)
        _audit("knowledge_query", target=entity_name)
        return {"entity": entity, "relationships": rels, "neighbors": neighbors}
    except Exception as exc:
        logger.error("Knowledge query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Knowledge query failed: {str(exc)}")


@app.get("/knowledge/search")
async def search_knowledge_graph(
    query: str = Query(..., description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """Search entities in the Knowledge Graph by name."""
    try:
        kg = _get_knowledge_graph()
        results = kg.search_entities(query, entity_type=entity_type, limit=limit)
        _audit("knowledge_search", target=query[:100])
        return results
    except Exception as exc:
        logger.error("Knowledge search failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Knowledge search failed: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 6. AGENTS — POST /agents/spawn, GET /agents/list
# ═══════════════════════════════════════════════════════════════════

@app.post("/agents/spawn")
async def spawn_agent(request: SpawnAgentRequest):
    """Spawn a sub-agent to handle a specific task."""
    try:
        from nexus.core.registry import get_registry
        registry = get_registry()
        instance = registry.spawn(request.agent_type, task=request.task)
        _audit("agent_spawn", target=request.agent_type, details={"task": request.task[:200]})
        return {
            "status": "spawned",
            "instance_id": instance.instance_id,
            "agent_type": request.agent_type,
            "task": request.task[:200],
        }
    except Exception as exc:
        logger.error("Agent spawn failed: %s", exc)
        _audit("agent_spawn", target=request.agent_type, outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Failed to spawn agent: {str(exc)}")


@app.get("/agents/list")
async def list_agents():
    """List all registered agent types and their instances."""
    try:
        from nexus.core.registry import get_registry
        registry = get_registry()
        _audit("agent_list")
        return {
            "types": registry.list_types(),
            "stats": registry.get_stats(),
        }
    except Exception as exc:
        logger.error("Agent list failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 7. CODE EXECUTION — POST /code/execute
# ═══════════════════════════════════════════════════════════════════

@app.post("/code/execute")
async def execute_code(request: CodeExecuteRequest):
    """Execute code (sandboxed or not) and return the output."""
    try:
        if request.sandboxed:
            from nexus.security.sandbox import LocalSandbox
            sandbox = LocalSandbox(timeout=request.timeout)
            result = await sandbox.execute_python(request.code, timeout=request.timeout)
            _audit("code_execute", target="sandboxed", details={
                "language": request.language,
                "timeout": request.timeout,
                "exit_code": result.exit_code,
            })
            return {
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:5000],
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "execution_time_ms": result.execution_time_ms,
            }
        else:
            from nexus.dev.code_executor import CodeExecutor
            executor = CodeExecutor(backend="local", timeout=request.timeout)
            result = await executor.execute(request.code, language=request.language, timeout=request.timeout)
            _audit("code_execute", target="local", details={
                "language": request.language,
                "timeout": request.timeout,
                "exit_code": result.exit_code,
            })
            return {
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:5000],
                "exit_code": result.exit_code,
                "language": result.language,
                "timed_out": result.timed_out,
                "execution_time_ms": result.execution_time_ms,
            }
    except Exception as exc:
        logger.error("Code execution failed: %s", exc)
        _audit("code_execute", outcome="failure", details={"error": str(exc)[:500]})
        raise HTTPException(status_code=500, detail=f"Code execution failed: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 8. SYSTEM — /status, /providers, /health, /config
# ═══════════════════════════════════════════════════════════════════

@app.get("/status")
async def get_system_status():
    """Get NEXUS agent status, version, and environment information."""
    try:
        from nexus.core.config import get_settings
        settings = get_settings()
        return {
            "agent": "NEXUS",
            "version": "0.1.0",
            "status": "running",
            "environment": settings.nexus_env.value,
            "providers_configured": settings.available_providers,
            "uptime_seconds": time.time() - _START_TIME,
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }
    except Exception as exc:
        logger.error("Status check failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(exc)}")


@app.get("/providers")
async def get_providers():
    """Get LLM provider status — available providers, default models, last call status."""
    try:
        router = _get_router()
        return router.get_provider_status()
    except Exception as exc:
        logger.error("Provider status failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not get provider status: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# Config API — In-app API key management
# ═══════════════════════════════════════════════════════════════════

_PROVIDER_KEY_MAP: dict[str, tuple[str, str]] = {
    # provider_id -> (env_var_name, display_name)
    "openai":       ("OPENAI_API_KEY",       "OpenAI"),
    "anthropic":    ("ANTHROPIC_API_KEY",    "Anthropic"),
    "gemini":       ("GOOGLE_API_KEY",       "Google AI"),
    "groq":         ("GROQ_API_KEY",         "Groq"),
    "openrouter":   ("OPENROUTER_API_KEY",   "OpenRouter"),
    "nvidia":       ("NVIDIA_API_KEY",       "NVIDIA"),
    "cerebras":     ("CEREBRAS_API_KEY",     "Cerebras"),
    "together":     ("TOGETHER_API_KEY",     "Together"),
    "glm":          ("ZAI_API_KEY",          "ZhipuAI / GLM"),
}

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def _mask_key(key: str | None) -> str:
    """Mask an API key for display: show first 4 and last 4 chars."""
    if not key or len(key) < 12:
        return "" if not key else "••••••••"
    return f"{key[:4]}{'•' * (len(key) - 8)}{key[-4:]}"


def _read_env_file() -> dict[str, str]:
    """Parse .env file into a dict."""
    env: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return env
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _write_env_file(updates: dict[str, str | None]) -> None:
    """Update .env file with new key-value pairs. None values remove the key."""
    lines: list[str] = []
    existing: dict[str, int] = {}  # key -> line index

    if _ENV_FILE.exists():
        for i, line in enumerate(_ENV_FILE.read_text(encoding="utf-8").splitlines()):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                existing[k] = i
            lines.append(line)

    for key, value in updates.items():
        if key in existing:
            if value is None:
                lines[existing[key]] = ""  # blank out removed key
            else:
                lines[existing[key]] = f"{key}={value}"
        elif value is not None:
            # Append new key
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"{key}={value}")

    _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.get("/config/api-keys")
async def get_api_keys():
    """Get masked API key status for all providers."""
    try:
        env = _read_env_file()
        from nexus.core.config import get_settings
        settings = get_settings()

        result = {}
        for provider_id, (env_var, display_name) in _PROVIDER_KEY_MAP.items():
            raw_key = env.get(env_var, "")
            # Also check settings (which reads from env vars at runtime)
            settings_key = getattr(settings, env_var.lower(), None) or raw_key
            has_key = bool(settings_key)
            result[provider_id] = {
                "name": display_name,
                "env_var": env_var,
                "configured": has_key,
                "masked": _mask_key(settings_key) if has_key else "",
            }
        return result
    except Exception as exc:
        logger.error("Get API keys failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


class ApiKeyUpdate(BaseModel):
    provider: str = Field(..., description="Provider ID (e.g. 'openai', 'gemini')")
    api_key: str = Field(default="", description="API key value (empty to remove)")


@app.post("/config/api-keys")
async def update_api_key(body: ApiKeyUpdate):
    """Update or remove an API key. Writes to .env and reloads config."""
    try:
        if body.provider not in _PROVIDER_KEY_MAP:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")

        env_var, display_name = _PROVIDER_KEY_MAP[body.provider]
        key_value = body.api_key.strip()

        # Update .env file
        _write_env_file({env_var: key_value if key_value else None})

        # Also update the current process environment so config picks it up immediately
        if key_value:
            os.environ[env_var] = key_value
        else:
            os.environ.pop(env_var, None)

        # Reload cached settings
        from nexus.core.config import reload_settings
        reload_settings()

        return {
            "status": "ok",
            "provider": body.provider,
            "configured": bool(key_value),
            "masked": _mask_key(key_value) if key_value else "",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Update API key failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint for production monitoring.
    
    Returns:
        dict: Health status with subsystem checks and metrics
    """
    import psutil
    from nexus.core.config import get_settings
    
    start_time = time.time()
    uptime = uptime_seconds()
    
    # Check subsystems
    subsystems = {}
    
    # Check ChromaDB
    try:
        from nexus.memory.chroma_service import get_chroma_client
        client = get_chroma_client()
        if client:
            subsystems["chromadb"] = {"status": "healthy", "latency_ms": round((time.time() - start_time) * 1000, 2)}
        else:
            subsystems["chromadb"] = {"status": "not_configured"}
    except Exception as e:
        subsystems["chromadb"] = {"status": "unhealthy", "error": str(e)}
    
    # Check LLM Providers
    try:
        from nexus.llm.router import get_router
        router = get_router()
        status = router.get_provider_status() if router else {}
        available = [k for k, v in status.items() if v.get("available")]
        subsystems["llm"] = {
            "status": "healthy" if len(available) > 0 else "degraded",
            "providers_count": len(available),
            "active_provider": get_settings().llm_default_provider
        }
    except Exception as e:
        subsystems["llm"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Memory System
    try:
        from nexus.memory.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        if orchestrator:
            stats = orchestrator.get_stats()
            subsystems["memory"] = {
                "status": "healthy",
                "total_embeddings": stats.get("total_embeddings", 0),
                "collections": stats.get("collections", {})
            }
        else:
            subsystems["memory"] = {"status": "not_initialized"}
    except Exception as e:
        subsystems["memory"] = {"status": "unhealthy", "error": str(e)}
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Determine overall status
    unhealthy_count = sum(1 for s in subsystems.values() if s.get("status") == "unhealthy")
    overall_status = "unhealthy" if unhealthy_count > 0 else ("degraded" if any(s.get("status") == "degraded" for s in subsystems.values()) else "healthy")
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(uptime, 2),
        "version": "0.1.0",
        "environment": os.getenv("NEXUS_ENV", "development"),
        "subsystems": subsystems,
        "system_metrics": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
        }
    }


def uptime_seconds() -> float:
    """Return the number of seconds since the server started."""
    return time.time() - _START_TIME


@app.get("/config")
async def get_config():
    """Get current NEXUS configuration (non-sensitive values only)."""
    try:
        from nexus.core.config import get_settings
        settings = get_settings()
        return {
            "environment": settings.nexus_env.value,
            "log_level": settings.nexus_log_level.value,
            "port": settings.nexus_port,
            "host": settings.nexus_host,
            "available_providers": settings.available_providers,
            "llm_default_provider": settings.llm_default_provider,
            "llm_default_model": settings.llm_default_model,
            "sandbox_enabled": settings.sandbox_enabled,
            "memory_default_top_k": settings.memory_default_top_k,
            "orchestrator_max_iterations": settings.orchestrator_max_iterations,
        }
    except Exception as exc:
        logger.error("Config retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not retrieve config: {str(exc)}")


@app.get("/metrics")
async def get_prometheus_metrics():
    """
    Prometheus metrics endpoint for production monitoring.
    
    Returns metrics in Prometheus text format for scraping by Prometheus server.
    Includes:
    - HTTP request rates and latencies
    - LLM token usage and costs
    - Memory system performance
    - Agent execution metrics
    - System health indicators
    
    Usage with Prometheus:
        scrape_configs:
          - job_name: 'nexus-agent'
            static_configs:
              - targets: ['localhost:8080']
            metrics_path: '/metrics'
    """
    from nexus.core.prometheus_metrics import metrics as prometheus_metrics
    from starlette.responses import Response
    
    # Update system metrics
    import psutil
    prometheus_metrics.set_system_cpu(psutil.cpu_percent(interval=0.1))
    prometheus_metrics.set_system_memory(psutil.virtual_memory().percent)
    prometheus_metrics.set_system_disk(psutil.disk_usage('/').percent)
    prometheus_metrics.set_system_uptime(uptime_seconds())
    
    return Response(
        content=prometheus_metrics.get_latest_metrics(),
        media_type=prometheus_metrics.get_content_type(),
    )


@app.post("/config")
async def update_config(request: Request):
    """
    Update NEXUS configuration at runtime.

    Accepts a JSON body with setting name → string value pairs.
    Only non-sensitive settings can be updated via API.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Allowed settings that can be updated via API (no secrets)
    ALLOWED_SETTINGS = {
        "llm_default_provider",
        "llm_default_model",
        "llm_fallback_chain",
        "llm_timeout_seconds",
        "sandbox_enabled",
        "memory_default_top_k",
        "orchestrator_max_iterations",
        "browser_service_enabled",
        "nexus_log_level",
    }

    updated = {}
    errors = {}

    from nexus.core.config import get_settings
    settings = get_settings()

    for key, value in body.items():
        if key not in ALLOWED_SETTINGS:
            errors[key] = f"Setting '{key}' cannot be updated via API (not in allowed list)"
            continue
        try:
            if hasattr(settings, key):
                setattr(settings, key, value)
                updated[key] = value
            else:
                errors[key] = f"Unknown setting: {key}"
        except Exception as exc:
            errors[key] = str(exc)

    _audit("config_update", details={"updated": list(updated.keys()), "errors": list(errors.keys())})

    return {
        "updated": updated,
        "errors": errors if errors else None,
        "status": "partial" if errors else "ok",
    }


# ═══════════════════════════════════════════════════════════════════
# 9. SECURITY — GET /security/audit
# ═══════════════════════════════════════════════════════════════════

@app.get("/security/audit")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=500, description="Maximum entries"),
    category: Optional[str] = Query(None, description="Filter by category"),
    since: Optional[str] = Query(None, description="ISO timestamp to start from"),
):
    """Get audit log entries."""
    try:
        audit = _get_audit_logger()
        from nexus.security.audit import AuditCategory

        cat_enum = None
        if category:
            try:
                cat_enum = AuditCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category '{category}'. Valid: {[c.value for c in AuditCategory]}",
                )

        entries = audit.query(category=cat_enum, since=since, limit=limit)
        return {"entries": entries, "count": len(entries)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audit log retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not retrieve audit log: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 10. WEBSOCKET — /ws (real-time event streaming)
# ═══════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent activity streaming.

    Any part of the backend can broadcast events via the EventBroadcaster,
    and all connected WebSocket clients receive them instantly.

    Authentication: pass ``?token=<api_key>`` query parameter.
    In development mode (no NEXUS_API_KEY set), the token is optional.

    Event format (JSON):
        {
            "type": "agent_thinking",
            "data": { ... },
            "timestamp": "2025-03-04T12:34:56.789Z",
            "event_id": "evt_abc123"
        }

    Supported event types: agent_thinking, agent_action, tool_call,
    tool_result, file_create, file_edit, code_building, task_step,
    task_done, error, avatar_expression, stream_token
    """
    await websocket.accept()

    # Authenticate via query param (accept first, then validate).
    await verify_ws_auth(websocket)

    broadcaster = _get_broadcaster()

    subscriber_id = await broadcaster.subscribe(websocket)

    try:
        # Run the event pump — this forwards queued events to the websocket
        await broadcaster.pump_subscriber(websocket)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", subscriber_id)
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", subscriber_id, exc)
    finally:
        await broadcaster.unsubscribe(websocket)


@app.get("/ws/status")
async def websocket_status():
    """Get the current WebSocket broadcaster status (subscriber count, etc.)."""
    broadcaster = _get_broadcaster()
    return broadcaster.get_status()


# ═══════════════════════════════════════════════════════════════════
# 10b. VIZ — Visualization event history & active builds
# ═══════════════════════════════════════════════════════════════════

@app.get("/viz/history/{build_id}")
async def get_viz_history(build_id: str):
    """
    Get visualization history for a specific build.

    Returns the list of VizEvent objects that were emitted during the
    build identified by ``build_id``. Each event includes type, title,
    content, progress, status, and metadata.
    """
    try:
        from nexus.core.viz_events import get_viz_emitter
        emitter = get_viz_emitter()
        events = emitter.get_build_history(build_id)
        return {
            "build_id": build_id,
            "count": len(events),
            "events": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "timestamp": e.timestamp,
                    "title": e.title,
                    "detail": e.detail,
                    "path": e.path,
                    "content": e.content[:5000] if e.content else None,
                    "language": e.language,
                    "diff": e.diff,
                    "progress": e.progress,
                    "status": e.status,
                    "artifact": e.artifact,
                    "metadata": e.metadata,
                }
                for e in events
            ],
        }
    except Exception as exc:
        logger.error("Viz history retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not retrieve viz history: {str(exc)}")


@app.get("/viz/active")
async def get_active_builds():
    """
    Get list of active build IDs currently being tracked by the visualization system.

    Returns each build ID along with a count of events emitted so far.
    """
    try:
        from nexus.core.viz_events import get_viz_emitter
        emitter = get_viz_emitter()
        active_ids = emitter.get_active_build_ids()
        builds = []
        for bid in active_ids:
            history = emitter.get_build_history(bid)
            builds.append({
                "build_id": bid,
                "event_count": len(history),
                "latest_title": history[-1].title if history else "",
                "latest_status": history[-1].status if history else "",
            })
        return {
            "count": len(builds),
            "builds": builds,
        }
    except Exception as exc:
        logger.error("Active builds retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not retrieve active builds: {str(exc)}")


# ═══════════════════════════════════════════════════════════════════
# 11. STREAMING CHAT — POST /chat/stream (Server-Sent Events)
# ═══════════════════════════════════════════════════════════════════

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint — returns Server-Sent Events (SSE) for
    token-by-token streaming of LLM responses.

    Each SSE event is a JSON object:
        event: token
        data: {"token": "Hello", "provider": "gemini", "model": "gemma-4"}

    Followed by a final event:
        event: done
        data: {"provider": "gemini", "model": "gemma-4", "usage": {...}}

    If an error occurs:
        event: error
        data: {"error": "message"}
    """
    broadcaster = _get_broadcaster()

    async def _stream_generator():
        """Async generator that yields SSE-formatted events."""
        start = time.monotonic()
        try:
            from nexus.llm.router import TaskComplexity
            router = _get_router()

            # Broadcast: agent thinking
            await broadcaster.broadcast("agent_thinking", {
                "action": "chat_stream",
                "provider": request.provider or "auto",
            })

            # Inject NEXUS awareness system prompt
            SYSTEM_PROMPT = (
                "You are NEXUS, a sovereign AI agent. "
                "You have access to the following capabilities:\n"
                "- Memory: search_memory(query, namespace), store_memory(text, namespace) — vector knowledge base\n"
                "- Knowledge Graph: knowledge_query(entity), knowledge_search(query) — entity/relationship graph\n"
                "- Web Search: web_search(query, num_results) — real-time web information\n"
                "- Code Execution: execute_code(code, language, timeout, sandboxed) — run Python/JS/Bash\n"
                "- File System: read_file(path), write_file(path, content), list_files(directory)\n"
                "- Task Orchestration: spawn_agent(task, agent_type) — create sub-agents for complex tasks\n"
                "- Reasoning: reason_react(task), reason_tot(task) — structured reasoning\n"
                "- System: get_status(), audit_query(limit) — system information\n"
                "- Avatar/Voice: avatar_speak(text), avatar_set_expression(expression) — TTS and VRM control\n\n"
                "When a user asks a question, consider which tools would help answer it. "
                "For current information, use web_search. For complex tasks, create a plan using tasks. "
                "For code questions, you can use execute_code. "
                "Always respond in French unless the user asks otherwise."
            )

            user_messages = list(request.messages)
            has_system = any(m.get("role") == "system" for m in user_messages)
            if not has_system:
                user_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_messages

            # Validate provider if specified
            if request.provider:
                try:
                    from nexus.llm.router import Provider
                    Provider(request.provider)
                except ValueError:
                    error_data = json.dumps({
                        "error": f"Unknown provider '{request.provider}'",
                    })
                    yield f"event: error\ndata: {error_data}\n\n"
                    return

            # For streaming, we call the LLM and then emit tokens.
            # Since the router doesn't yet natively stream token-by-token,
            # we simulate streaming by chunking the response.
            #
            # Future improvement: use router.complete(stream=True) when it
            # returns an async generator of tokens.

            # Broadcast: tool call (LLM completion)
            await broadcaster.broadcast("tool_call", {
                "tool": "llm_stream",
                "provider": request.provider or "auto",
                "model": request.model or "default",
            })

            # --- Try to use real streaming via litellm ---
            stream_succeeded = False
            try:
                from nexus.llm.router import PROVIDER_DEFAULT_MODELS as _PROVIDER_MODELS

                providers = router.select_provider(
                    TaskComplexity.MEDIUM, request.provider
                )
                if not providers:
                    raise Exception("No providers available")

                use_provider = providers[0]
                use_model = request.model or _PROVIDER_MODELS.get(use_provider, "gpt-4o")

                # Try litellm streaming
                import litellm

                litellm_model_map = {
                    "openai": f"openai/{use_model}",
                    "anthropic": f"anthropic/{use_model}",
                    "gemini": f"gemini/{use_model}",
                    "groq": f"groq/{use_model}",
                    "openrouter": f"openrouter/{use_model}",
                    "nvidia": f"nvidia/{use_model}",
                    "cerebras": f"cerebras/{use_model}",
                    "together": f"together_ai/{use_model}",
                }

                litellm_model = litellm_model_map.get(use_provider.value, use_model)

                call_kwargs = {
                    "model": litellm_model,
                    "messages": user_messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True,
                    "timeout": router.settings.llm_timeout_seconds,
                }

                # Pass API key directly for known providers
                api_key_map = {
                    "gemini": router.settings.google_api_key,
                    "groq": router.settings.groq_api_key,
                    "openrouter": router.settings.openrouter_api_key,
                    "nvidia": router.settings.nvidia_api_key,
                    "cerebras": router.settings.cerebras_api_key,
                    "together": router.settings.together_api_key,
                }
                if use_provider.value in api_key_map and api_key_map[use_provider.value]:
                    call_kwargs["api_key"] = api_key_map[use_provider.value]

                # Call litellm in a thread to avoid blocking the event loop
                response_stream = await asyncio.to_thread(
                    litellm.completion, **call_kwargs
                )

                full_content = []
                usage = {}
                for chunk in response_stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        token = delta.content
                        full_content.append(token)

                        # Broadcast stream_token to WebSocket subscribers
                        await broadcaster.broadcast("stream_token", {
                            "token": token,
                            "provider": use_provider.value,
                            "model": use_model,
                        })

                        # Yield SSE event
                        token_data = json.dumps({
                            "token": token,
                            "provider": use_provider.value,
                            "model": use_model,
                        })
                        yield f"event: token\ndata: {token_data}\n\n"

                    # Check for finish
                    if chunk.choices and chunk.choices[0].finish_reason:
                        if hasattr(chunk, "usage") and chunk.usage:
                            usage = {
                                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                                "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                            }

                stream_succeeded = True
                latency = (time.monotonic() - start) * 1000

                # Broadcast: tool result
                await broadcaster.broadcast("tool_result", {
                    "tool": "llm_stream",
                    "provider": use_provider.value,
                    "model": use_model,
                    "latency_ms": latency,
                    "content_length": len("".join(full_content)),
                })

                # Broadcast: agent action
                await broadcaster.broadcast("agent_action", {
                    "action": "chat_stream_response",
                    "provider": use_provider.value,
                    "model": use_model,
                    "content_length": len("".join(full_content)),
                })

                # Yield final done event
                done_data = json.dumps({
                    "provider": use_provider.value,
                    "model": use_model,
                    "usage": usage,
                    "latency_ms": latency,
                })
                yield f"event: done\ndata: {done_data}\n\n"

                _audit("chat_stream", target=use_provider.value, details={"latency_ms": latency})

            except (ImportError, Exception) as stream_exc:
                if not stream_succeeded:
                    logger.debug("Streaming not available, falling back to chunked: %s", stream_exc)
                    # Fallback: do a regular completion and chunk the response
                    response = await router.complete(
                        messages=user_messages,
                        model=request.model,
                        provider=request.provider,
                        task_complexity=TaskComplexity.MEDIUM,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                    )

                    content = response.content
                    latency = (time.monotonic() - start) * 1000

                    # Simulate streaming by chunking the response into word-size pieces
                    words = content.split(" ")
                    for i, word in enumerate(words):
                        token = word if i == 0 else f" {word}"

                        # Broadcast stream_token to WebSocket subscribers
                        await broadcaster.broadcast("stream_token", {
                            "token": token,
                            "provider": response.provider.value,
                            "model": response.model,
                        })

                        token_data = json.dumps({
                            "token": token,
                            "provider": response.provider.value,
                            "model": response.model,
                        })
                        yield f"event: token\ndata: {token_data}\n\n"

                        # Small delay to simulate streaming feel
                        await asyncio.sleep(0.02)

                    # Broadcast: tool result
                    await broadcaster.broadcast("tool_result", {
                        "tool": "llm_stream",
                        "provider": response.provider.value,
                        "model": response.model,
                        "latency_ms": latency,
                        "content_length": len(content),
                    })

                    # Yield final done event
                    done_data = json.dumps({
                        "provider": response.provider.value,
                        "model": response.model,
                        "usage": response.usage,
                        "latency_ms": latency,
                    })
                    yield f"event: done\ndata: {done_data}\n\n"

                    _audit("chat_stream", target=response.provider.value, details={"latency_ms": latency, "mode": "chunked_fallback"})

        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Streaming chat failed: %s", exc)
            _audit("chat_stream", outcome="failure", details={"error": str(exc)[:500]})
            await broadcaster.broadcast("error", {
                "action": "chat_stream",
                "error": str(exc)[:500],
            })
            error_data = json.dumps({"error": str(exc)[:500]})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# Global Exception Handler — ensure all errors return clean JSON
# ═══════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler that returns human-readable JSON errors."""
    logger.error("Unhandled exception on %s %s: %s\n%s", request.method, request.url.path, exc, traceback.format_exc())
    _audit("unhandled_error", target=request.url.path, outcome="failure", details={"error": str(exc)[:500]})

    return {
        "detail": f"An unexpected error occurred: {str(exc)}",
        "error_type": type(exc).__name__,
        "path": request.url.path,
    }
