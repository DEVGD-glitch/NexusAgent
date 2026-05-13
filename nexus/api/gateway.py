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

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Security helpers
# ═══════════════════════════════════════════════════════════════════

security_scheme = HTTPBearer(auto_error=False)

DEFAULT_SECRET_KEY = "dev-test-key-not-for-production"
FALLBACK_SECRET_KEY = "change-me-to-a-secure-random-string"


def _warn_default_key():
    """Emit a single warning if NEXUS_SECRET_KEY is the default value."""
    from nexus.core.config import get_settings
    sk = get_settings().nexus_secret_key
    if sk in (DEFAULT_SECRET_KEY, FALLBACK_SECRET_KEY):
        logger.warning(
            "NEXUS_SECRET_KEY is set to the default value '%s...'. "
            "Generate a strong random key with: python -c \"import secrets; print(secrets.token_hex(32))\"",
            sk[:20],
        )


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)):
    """Optional token verification. In production, rejects missing/invalid tokens."""
    from nexus.core.config import get_settings
    settings = get_settings()

    if settings.nexus_env.value == "production":
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        token = credentials.credentials
        expected = settings.nexus_secret_key
        if token != expected:
            raise HTTPException(status_code=403, detail="Invalid authentication token")


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
)

_warn_default_key()

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
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate Limiter ────────────────────────────────────────────────

_limiter = None


def _get_limiter():
    global _limiter
    if _limiter is None:
        from nexus.security.rate_limiter import RateLimiter
        _limiter = RateLimiter()
    return _limiter


# ── Auth Middleware (production only) ─────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Reject unauthenticated requests in production mode + rate limiting."""
    if _is_production:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        token = auth_header.removeprefix("Bearer ")
        from nexus.core.config import get_settings
        expected = get_settings().nexus_secret_key
        if token != expected:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "Invalid authentication token"})

    # Rate limiting for all environments
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


class RunRequest(BaseModel):
    task: str = Field(..., description="Task description", min_length=1)
    provider: Optional[str] = Field(None, description="Preferred LLM provider")


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
    """
    start = time.monotonic()
    try:
        from nexus.llm.router import TaskComplexity
        router = _get_router()

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

        response = await router.complete(
            messages=user_messages,
            model=request.model,
            provider=request.provider,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        latency = (time.monotonic() - start) * 1000
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
        # Check if it's an "all providers failed" error
        error_msg = str(exc)
        if "All LLM providers failed" in error_msg:
            raise HTTPException(
                status_code=502,
                detail=f"All LLM providers failed. Check your API keys in .env and try a different provider. Error: {error_msg}",
            )
        raise HTTPException(status_code=500, detail=f"Chat failed: {error_msg}")


# ═══════════════════════════════════════════════════════════════════
# 2. RUN TASK — POST /run
# ═══════════════════════════════════════════════════════════════════

@app.post("/run")
async def run_task(request: RunRequest):
    """
    Run a task through the NEXUS Plan-Execute-Reflect orchestrator.

    This is the primary endpoint for complex multi-step tasks.
    """
    start = time.monotonic()
    try:
        from nexus.orchestrator.langgraph_engine import run_nexus_task

        result = await run_nexus_task(
            task=request.task,
            messages=[],
        )

        latency = (time.monotonic() - start) * 1000
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
        raise HTTPException(status_code=500, detail=f"Task failed: {str(exc)}")


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
    from nexus.reasoning.react import ReactReasoner
    reasoner = ReactReasoner(max_iterations=max_iterations)
    result = await reasoner.solve(task)
    return {
        "answer": result.answer,
        "iterations": result.iterations_used,
        "reasoning_trace": [
            {"thought": s.thought, "action": s.action, "observation": s.observation}
            for s in result.steps
        ],
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


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


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
