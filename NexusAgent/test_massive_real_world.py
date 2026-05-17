"""
NEXUS Agent — Massive Real-World Integration Test Suite
Tests ALL tools, skills, MCP, memory, agents, LLM providers, code execution, etc.
"""
import asyncio
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE = "http://127.0.0.1:8081"
TIMEOUT = 30.0

@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float = 0.0
    detail: str = ""
    error: str = ""

results: list[TestResult] = []

async def api(c: httpx.AsyncClient, method: str, path: str, **kw) -> tuple[int, Any]:
    r = await c.request(method, path, **kw)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text

async def run_test(name: str, coro):
    t0 = time.perf_counter()
    try:
        detail = await coro
        ms = (time.perf_counter() - t0) * 1000
        results.append(TestResult(name, True, ms, str(detail)[:200]))
        print(f"  [PASS] {name} ({ms:.0f}ms)")
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        results.append(TestResult(name, False, ms, error=f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name} ({ms:.0f}ms) — {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. INFRASTRUCTURE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_health(c):
    code, data = await api(c, "GET", "/health")
    assert code == 200, f"HTTP {code}"
    assert data["status"] == "healthy"
    return f"status={data['status']}, uptime={data.get('uptime_seconds',0):.0f}s"

async def test_metrics(c):
    code, data = await api(c, "GET", "/metrics")
    assert code == 200, f"HTTP {code}"
    return f"metrics keys: {list(data.keys()) if isinstance(data, dict) else 'ok'}"

async def test_status(c):
    code, data = await api(c, "GET", "/status")
    assert code == 200, f"HTTP {code}"
    return f"status ok"

async def test_config(c):
    code, data = await api(c, "GET", "/config")
    assert code == 200, f"HTTP {code}"
    return f"config ok"

async def test_capabilities(c):
    code, data = await api(c, "GET", "/capabilities")
    assert code == 200, f"HTTP {code}"
    return f"capabilities ok"

async def test_providers(c):
    code, data = await api(c, "GET", "/providers")
    assert code == 200, f"HTTP {code}"
    return f"providers: {data if isinstance(data, str) else list(data.keys()) if isinstance(data, dict) else 'ok'}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. LLM PROVIDERS — gemma-4-31b-it + GLM free models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_chat_gemma4(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [{"role": "user", "content": "Dis bonjour en une phrase courte"}],
        "model": "gemma-4-31b-it"
    })
    assert code == 200, f"HTTP {code}: {data}"
    return f"gemma-4-31b-it: {str(data)[:150]}"

async def test_chat_glm4_flash(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [{"role": "user", "content": "Dis bonjour en une phrase courte"}],
        "model": "glm-4-flash"
    })
    assert code == 200, f"HTTP {code}: {data}"
    return f"glm-4-flash: {str(data)[:150]}"

async def test_chat_glm45_flash(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [{"role": "user", "content": "Dis bonjour en une phrase courte"}],
        "model": "glm-4.5-flash"
    })
    assert code == 200, f"HTTP {code}: {data}"
    return f"glm-4.5-flash: {str(data)[:150]}"

async def test_chat_glm47_flash(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [{"role": "user", "content": "Dis bonjour en une phrase courte"}],
        "model": "glm-4.7-flash"
    })
    assert code == 200, f"HTTP {code}: {data}"
    return f"glm-4.7-flash: {str(data)[:150]}"

async def test_chat_glm4v_flash(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [{"role": "user", "content": "Decris cette image en une phrase"}],
        "model": "glm-4v-flash"
    })
    # Vision model without image — should still respond
    return f"glm-4v-flash: HTTP {code}, {str(data)[:100]}"

async def test_chat_stream(c):
    """Test SSE streaming endpoint."""
    async with c.stream("POST", "/chat/stream", json={
        "messages": [{"role": "user", "content": "Compte de 1 a 5"}],
        "model": "gemma-4-31b-it"
    }, timeout=30.0) as r:
        assert r.status_code == 200, f"HTTP {r.status_code}"
        chunks = []
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                chunks.append(line[6:])
            if len(chunks) >= 3:
                break
        return f"stream chunks: {len(chunks)}"

async def test_chat_system_prompt(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [
            {"role": "system", "content": "Tu es un pirate. Reponds toujours en parlant comme un pirate."},
            {"role": "user", "content": "Bonjour!"}
        ],
        "model": "gemma-4-31b-it"
    })
    assert code == 200, f"HTTP {code}"
    return f"system prompt: {str(data)[:150]}"

async def test_chat_multi_turn(c):
    code, data = await api(c, "POST", "/chat", json={
        "messages": [
            {"role": "user", "content": "Je m'appelle Alice"},
            {"role": "assistant", "content": "Bonjour Alice!"},
            {"role": "user", "content": "Comment je m'appelle?"}
        ],
        "model": "glm-4-flash"
    })
    assert code == 200, f"HTTP {code}"
    return f"multi-turn: {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. MEMORY SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_memory_stats(c):
    code, data = await api(c, "GET", "/memory/stats")
    assert code == 200, f"HTTP {code}"
    return f"memory stats: {str(data)[:150]}"

async def test_memory_store(c):
    code, data = await api(c, "POST", "/memory/store", json={
        "content": "NEXUS Agent est un assistant IA multi-modèles",
        "namespace": "test",
        "metadata": {"source": "integration_test"}
    })
    assert code == 200, f"HTTP {code}"
    return f"stored: {str(data)[:150]}"

async def test_memory_recall(c):
    code, data = await api(c, "POST", "/memory/recall", json={
        "query": "assistant IA multi-modèles",
        "namespace": "test",
        "top_k": 3
    })
    assert code == 200, f"HTTP {code}"
    return f"recalled: {str(data)[:150]}"

async def test_memory_namespaces(c):
    code, data = await api(c, "GET", "/memory/namespaces")
    assert code == 200, f"HTTP {code}"
    return f"namespaces: {str(data)[:150]}"

async def test_memory_semantic_add(c):
    code, data = await api(c, "POST", "/memory/semantic/add_fact", json={
        "subject": "NEXUS",
        "predicate": "supports",
        "object": "multi-model LLM",
        "namespace": "test"
    })
    return f"semantic add: HTTP {code}, {str(data)[:100]}"

async def test_memory_semantic_query(c):
    code, data = await api(c, "POST", "/memory/semantic/query", json={
        "query": "multi-model",
        "namespace": "test"
    })
    return f"semantic query: HTTP {code}, {str(data)[:100]}"

async def test_memory_episodic_record(c):
    code, data = await api(c, "POST", "/memory/episodic/record", json={
        "event": "Integration test executed",
        "context": {"test": True, "timestamp": time.time()},
        "namespace": "test"
    })
    return f"episodic record: HTTP {code}, {str(data)[:100]}"

async def test_memory_episodic_recall(c):
    code, data = await api(c, "POST", "/memory/episodic/recall", json={
        "query": "Integration test",
        "namespace": "test"
    })
    return f"episodic recall: HTTP {code}, {str(data)[:100]}"

async def test_memory_identity(c):
    code, data = await api(c, "GET", "/memory/identity/profile")
    return f"identity: HTTP {code}, {str(data)[:100]}"

async def test_memory_procedural(c):
    code, data = await api(c, "POST", "/memory/procedural/find_relevant", json={
        "context": "user wants to search the web",
        "namespace": "test"
    })
    return f"procedural: HTTP {code}, {str(data)[:100]}"

async def test_memory_compact(c):
    code, data = await api(c, "POST", "/memory/compact", json={"namespace": "test"})
    return f"compact: HTTP {code}, {str(data)[:100]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. SKILLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_skills_list(c):
    code, data = await api(c, "GET", "/skills")
    assert code == 200, f"HTTP {code}"
    if isinstance(data, list):
        return f"skills: {len(data)} found"
    return f"skills: {str(data)[:150]}"

async def test_skills_execute(c):
    code, data = await api(c, "POST", "/skills/execute", json={
        "skill": "web_search",
        "input": {"query": "NEXUS agent AI 2025"}
    })
    return f"skill execute: HTTP {code}, {str(data)[:150]}"

async def test_skills_crystallize(c):
    code, data = await api(c, "POST", "/skills/crystallize", json={
        "pattern": "search and summarize web results",
        "namespace": "test"
    })
    return f"crystallize: HTTP {code}, {str(data)[:100]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. MCP TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_mcp_list(c):
    code, data = await api(c, "GET", "/api/mcp")
    assert code == 200, f"HTTP {code}"
    return f"mcp servers: {str(data)[:150]}"

async def test_mcp_available(c):
    code, data = await api(c, "GET", "/api/mcp/available")
    return f"mcp available: HTTP {code}, {str(data)[:150]}"

async def test_mcp_builtins(c):
    code, data = await api(c, "GET", "/api/mcp/builtins")
    return f"mcp builtins: HTTP {code}, {str(data)[:150]}"

async def test_mcp_search(c):
    code, data = await api(c, "GET", "/api/mcp/search", params={"q": "filesystem"})
    return f"mcp search: HTTP {code}, {str(data)[:150]}"

async def test_tools_list(c):
    code, data = await api(c, "GET", "/api/tools")
    assert code == 200, f"HTTP {code}"
    return f"tools: {str(data)[:150]}"

async def test_tools_stats(c):
    code, data = await api(c, "GET", "/api/tools/stats")
    return f"tools stats: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. CODE EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_code_python(c):
    code, data = await api(c, "POST", "/code/execute", json={
        "language": "python",
        "code": "print(sum(range(100)))"
    })
    assert code == 200, f"HTTP {code}: {data}"
    return f"python exec: {str(data)[:150]}"

async def test_code_javascript(c):
    code, data = await api(c, "POST", "/code/execute", json={
        "language": "javascript",
        "code": "console.log(Array.from({length:10}, (_,i)=>i*i).join(', '))"
    })
    return f"js exec: HTTP {code}, {str(data)[:150]}"

async def test_code_error_handling(c):
    code, data = await api(c, "POST", "/code/execute", json={
        "language": "python",
        "code": "raise ValueError('test error')"
    })
    return f"error handling: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. AGENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_agents_list(c):
    code, data = await api(c, "GET", "/agents/list")
    assert code == 200, f"HTTP {code}"
    return f"agents: {str(data)[:150]}"

async def test_agents_spawn_developer(c):
    code, data = await api(c, "POST", "/agents/spawn", json={
        "agent_type": "developer",
        "task": "Ecrit une fonction Python qui calcule la factorielle",
        "model": "glm-4-flash"
    })
    return f"spawn developer: HTTP {code}, {str(data)[:150]}"

async def test_agents_spawn_researcher(c):
    code, data = await api(c, "POST", "/agents/spawn", json={
        "agent_type": "researcher",
        "task": "Recherche les dernieres avancees en IA generative 2025",
        "model": "gemma-4-31b-it"
    })
    return f"spawn researcher: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. SECURITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_security_audit(c):
    code, data = await api(c, "GET", "/security/audit")
    return f"security audit: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. KNOWLEDGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_knowledge_search(c):
    code, data = await api(c, "POST", "/knowledge/search", json={
        "query": "agent IA multi-modèles",
        "limit": 5
    })
    return f"knowledge search: HTTP {code}, {str(data)[:150]}"

async def test_knowledge_query(c):
    code, data = await api(c, "POST", "/knowledge/query", json={
        "question": "Qu'est-ce que NEXUS Agent?"
    })
    return f"knowledge query: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10. VOICE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_voice_voices(c):
    code, data = await api(c, "GET", "/voice/voices")
    return f"voices: HTTP {code}, {str(data)[:150]}"

async def test_voice_synthesize(c):
    code, data = await api(c, "POST", "/voice/synthesize", json={
        "text": "Bonjour, je suis NEXUS",
        "voice": "default"
    })
    return f"synthesize: HTTP {code}, len={len(str(data))}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 11. CRONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_crons_list(c):
    code, data = await api(c, "GET", "/crons/list")
    return f"crons: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 12. VISUALIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_viz_active(c):
    code, data = await api(c, "GET", "/viz/active")
    return f"viz active: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 13. SEARCH MEMORY TOOL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_search_memory(c):
    code, data = await api(c, "POST", "/tools/search_memory", json={
        "query": "NEXUS",
        "limit": 5
    })
    return f"search memory: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 14. WEB SEARCH (via tool execute)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_web_search_tool(c):
    code, data = await api(c, "POST", "/api/tools/web_search/execute", json={
        "query": "latest AI news 2025"
    })
    return f"web search: HTTP {code}, {str(data)[:150]}"

async def test_web_scrape_tool(c):
    code, data = await api(c, "POST", "/api/tools/web_scrape/execute", json={
        "url": "https://example.com"
    })
    return f"web scrape: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 15. RUN (arbitrary task)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def test_run_task(c):
    code, data = await api(c, "POST", "/run", json={
        "task": "Liste les 3 premiers nombres premiers",
        "model": "glm-4-flash"
    })
    return f"run task: HTTP {code}, {str(data)[:150]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    print(f"\n{'='*60}")
    print(f"  NEXUS Agent — Massive Real-World Test Suite")
    print(f"  Target: {BASE}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        # Check server is up
        try:
            r = await c.get("/health")
            r.raise_for_status()
        except Exception as e:
            print(f"[FATAL] Server not reachable: {e}")
            sys.exit(1)

        sections = [
            ("INFRASTRUCTURE", [
                test_health, test_metrics, test_status, test_config,
                test_capabilities, test_providers,
            ]),
            ("LLM PROVIDERS", [
                test_chat_gemma4, test_chat_glm4_flash, test_chat_glm45_flash,
                test_chat_glm47_flash, test_chat_glm4v_flash,
                test_chat_stream, test_chat_system_prompt, test_chat_multi_turn,
            ]),
            ("MEMORY SYSTEM", [
                test_memory_stats, test_memory_store, test_memory_recall,
                test_memory_namespaces, test_memory_semantic_add,
                test_memory_semantic_query, test_memory_episodic_record,
                test_memory_episodic_recall, test_memory_identity,
                test_memory_procedural, test_memory_compact,
            ]),
            ("SKILLS", [
                test_skills_list, test_skills_execute, test_skills_crystallize,
            ]),
            ("MCP TOOLS", [
                test_mcp_list, test_mcp_available, test_mcp_builtins,
                test_mcp_search, test_tools_list, test_tools_stats,
            ]),
            ("CODE EXECUTION", [
                test_code_python, test_code_javascript, test_code_error_handling,
            ]),
            ("AGENTS", [
                test_agents_list, test_agents_spawn_developer,
                test_agents_spawn_researcher,
            ]),
            ("SECURITY", [test_security_audit]),
            ("KNOWLEDGE", [test_knowledge_search, test_knowledge_query]),
            ("VOICE", [test_voice_voices, test_voice_synthesize]),
            ("CRONS", [test_crons_list]),
            ("VISUALIZATION", [test_viz_active]),
            ("SEARCH", [test_search_memory, test_web_search_tool, test_web_scrape_tool]),
            ("RUN TASK", [test_run_task]),
        ]

        total_tests = sum(len(tests) for _, tests in sections)
        print(f"Running {total_tests} tests across {len(sections)} sections...\n")

        for section_name, tests in sections:
            print(f"\n[{section_name}]")
            for test_fn in tests:
                await run_test(test_fn.__name__.replace("test_", ""), test_fn(c))

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_ms = sum(r.duration_ms for r in results)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{len(results)} passed, {failed} failed")
    print(f"  Total time: {total_ms/1000:.1f}s")
    print(f"{'='*60}")

    if failed:
        print(f"\n[FAILURES]")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.error}")

    return failed == 0

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
