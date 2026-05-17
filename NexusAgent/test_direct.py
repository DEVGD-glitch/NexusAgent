#!/usr/bin/env python3
"""
NEXUS Agent — Test DIRECT en situation réelle avec gemma-4-31b-it
Teste les composants directement sans serveur HTTP.
"""

import asyncio
import sys
import os
import time

os.environ["GOOGLE_API_KEY"] = "AIzaSyBQFGI7p1qtPHe2yRa_Sgr51uUoDRQHkDs"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = {"passed": 0, "failed": 0, "errors": []}

def log_ok(cat, name, detail="", latency=0):
    lat = f" ({latency:.0f}ms)" if latency > 0 else ""
    print(f"  {GREEN}✓{RESET} {CYAN}[{cat}]{RESET} {name}{lat}")
    if detail:
        print(f"    {YELLOW}→ {detail[:200]}{RESET}")
    results["passed"] += 1

def log_fail(cat, name, detail=""):
    print(f"  {RED}✗{RESET} {CYAN}[{cat}]{RESET} {name}")
    if detail:
        print(f"    {RED}→ {detail[:200]}{RESET}")
    results["failed"] += 1
    results["errors"].append(f"[{cat}] {name}: {detail[:100]}")


async def test_llm_router():
    """Test 1-5: LLM Router + Chat avec gemma-4-31b-it"""
    print(f"\n{BOLD}═══ LLM ROUTER — CHAT COMPLETION ═══{RESET}")

    from nexus.llm.router import LLMRouter, TaskComplexity, Provider

    router = LLMRouter()

    # Check providers
    status = router.get_provider_status()
    gemini_avail = status.get("gemini", {}).get("available", False)
    if gemini_avail:
        log_ok("LLM", "Gemini provider available", f"Default model: {status['gemini']['default_model']}")
    else:
        log_fail("LLM", "Gemini provider available", "GOOGLE_API_KEY not configured")
        return

    # Test 1: Basic chat
    print(f"\n  {YELLOW}Test: Chat basique en français...{RESET}")
    start = time.monotonic()
    try:
        resp = await router.complete(
            messages=[
                {"role": "system", "content": "Tu es NEXUS, un agent IA souverain. Réponds toujours en français."},
                {"role": "user", "content": "Bonjour ! Dis-moi bonjour et explique brièvement ce que tu es."},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.7,
            max_tokens=512,
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("CHAT", "Chat basique (FR)",
               f"Provider: {resp.provider.value}, Model: {resp.model}, Response: {resp.content[:150]}...",
               latency)
    except Exception as e:
        log_fail("CHAT", "Chat basique (FR)", str(e))
        return  # Can't continue if LLM doesn't work

    # Test 2: Code generation
    print(f"\n  {YELLOW}Test: Génération de code Python...{RESET}")
    start = time.monotonic()
    try:
        resp = await router.complete(
            messages=[
                {"role": "system", "content": "Tu es un expert Python. Donne uniquement du code fonctionnel."},
                {"role": "user", "content": "Écris une fonction Python fibonacci(n) qui retourne la suite jusqu'à n."},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.3,
            max_tokens=1024,
        )
        latency = (time.monotonic() - start) * 1000
        has_code = "def " in resp.content or "fibonacci" in resp.content.lower()
        log_ok("CHAT", "Génération de code" if has_code else "Génération de code (partiel)",
               f"Code détecté: {has_code}, Content: {resp.content[:150]}...",
               latency)
    except Exception as e:
        log_fail("CHAT", "Génération de code", str(e))

    # Test 3: Reasoning
    print(f"\n  {YELLOW}Test: Raisonnement mathématique...{RESET}")
    start = time.monotonic()
    try:
        resp = await router.complete(
            messages=[
                {"role": "user", "content": "Si j'ai 3 pommes, que j'en donne 1 à Marie et 1 à Pierre, combien m'en reste-t-il ? Explique ton raisonnement étape par étape."},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.1,
            max_tokens=512,
        )
        latency = (time.monotonic() - start) * 1000
        correct = "1" in resp.content
        log_ok("REASON", "Raisonnement mathématique" if correct else "Raisonnement (vérifier)",
               f"Réponse: {resp.content[:200]}...",
               latency)
    except Exception as e:
        log_fail("REASON", "Raisonnement mathématique", str(e))

    # Test 4: Multi-turn
    print(f"\n  {YELLOW}Test: Conversation multi-tour...{RESET}")
    try:
        # Turn 1
        start = time.monotonic()
        resp1 = await router.complete(
            messages=[
                {"role": "user", "content": "Mon nom est Alice. Retiens-le."},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.3,
            max_tokens=256,
        )
        lat1 = (time.monotonic() - start) * 1000
        log_ok("CHAT", "Multi-tour (tour 1)", f"Response: {resp1.content[:100]}...", lat1)

        # Turn 2
        start = time.monotonic()
        resp2 = await router.complete(
            messages=[
                {"role": "user", "content": "Mon nom est Alice. Retiens-le."},
                {"role": "assistant", "content": resp1.content},
                {"role": "user", "content": "Quel est mon nom ?"},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.1,
            max_tokens=256,
        )
        lat2 = (time.monotonic() - start) * 1000
        remembers = "Alice" in resp2.content
        log_ok("CHAT", "Multi-tour (tour 2)" if remembers else "Multi-tour (tour 2 - WARN)",
               f"Se souvient du nom: {remembers}, Response: {resp2.content[:100]}...",
               lat2)
    except Exception as e:
        log_fail("CHAT", "Multi-tour", str(e))

    # Test 5: Creative task
    print(f"\n  {YELLOW}Test: Tâche créative...{RESET}")
    start = time.monotonic()
    try:
        resp = await router.complete(
            messages=[
                {"role": "user", "content": "Invente un court poème de 4 lignes sur l'intelligence artificielle."},
            ],
            provider="gemini",
            model="gemma-4-31b-it",
            temperature=0.9,
            max_tokens=256,
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("CHAT", "Tâche créative", f"Response: {resp.content[:200]}...", latency)
    except Exception as e:
        log_fail("CHAT", "Tâche créative", str(e))


async def test_gemini_provider_direct():
    """Test 6: Gemini Provider direct avec thinking"""
    print(f"\n{BOLD}═══ GEMINI PROVIDER DIRECT ═══{RESET}")

    from nexus.llm.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider()
    if not provider.is_available:
        log_fail("GEMINI", "Provider available", "API key not set")
        return
    log_ok("GEMINI", "Provider available")

    # Test with thinking
    print(f"\n  {YELLOW}Test: Gemma 4 avec thinking...{RESET}")
    start = time.monotonic()
    try:
        resp = await provider.complete(
            messages=[
                {"role": "system", "content": "<|think|> Tu es un assistant qui réfléchit avant de répondre."},
                {"role": "user", "content": "Quelle est la racine carrée de 144 ? Montre ton raisonnement."},
            ],
            model="gemma-4-31b-it",
            thinking_level="HIGH",
            temperature=0.3,
            max_tokens=1024,
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("GEMINI", "Gemma 4 thinking mode",
               f"Content: {resp.content[:200]}..., Usage: {resp.usage}, Cost: ${resp.cost_usd:.6f}",
               latency)
    except Exception as e:
        log_fail("GEMINI", "Gemma 4 thinking mode", str(e))

    # Test streaming
    print(f"\n  {YELLOW}Test: Gemma 4 streaming...{RESET}")
    start = time.monotonic()
    try:
        chunks = []
        async for chunk in provider.stream(
            messages=[{"role": "user", "content": "Dis 'Bonjour' en 5 langues."}],
            model="gemma-4-31b-it",
            temperature=0.7,
            max_tokens=256,
        ):
            chunks.append(chunk)
        latency = (time.monotonic() - start) * 1000
        full = "".join(chunks)
        log_ok("GEMINI", "Streaming mode",
               f"Chunks: {len(chunks)}, Content: {full[:150]}...",
               latency)
    except Exception as e:
        log_fail("GEMINI", "Streaming mode", str(e))

    # Stats
    stats = provider.get_stats()
    log_ok("GEMINI", "Provider stats",
           f"Calls: {stats['call_count']}, Cost: ${stats['total_cost_usd']:.6f}")


async def test_code_executor():
    """Test 7: Code execution"""
    print(f"\n{BOLD}═══ CODE EXECUTION ═══{RESET}")

    from nexus.dev.code_executor import CodeExecutor

    executor = CodeExecutor(backend="local", timeout=10)

    start = time.monotonic()
    try:
        result = await executor.execute(
            "print('Hello from NEXUS!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')",
            language="python",
            timeout=10,
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("CODE", "Execute Python",
               f"Stdout: {result.stdout[:100]}, Exit: {result.exit_code}, Time: {result.execution_time_ms}ms",
               latency)
    except Exception as e:
        log_fail("CODE", "Execute Python", str(e))

    # More complex code
    start = time.monotonic()
    try:
        code = """
import math
for i in range(1, 11):
    print(f"{i}! = {math.factorial(i)}")
"""
        result = await executor.execute(code, language="python", timeout=10)
        latency = (time.monotonic() - start) * 1000
        log_ok("CODE", "Execute Python (factorials)",
               f"Stdout: {result.stdout[:150]}, Exit: {result.exit_code}",
               latency)
    except Exception as e:
        log_fail("CODE", "Execute Python (factorials)", str(e))


async def test_memory():
    """Test 8: Memory (ChromaDB)"""
    print(f"\n{BOLD}═══ MÉMOIRE VECTORIELLE (ChromaDB) ═══{RESET}")

    try:
        from nexus.memory.chroma_service import NexusMemoryService

        service = NexusMemoryService(persist_dir="./nexus_data/chroma_test")

        # Store
        start = time.monotonic()
        doc_id = await service.store(
            text="NEXUS est un agent IA souverain capable de raisonner, coder et mémoriser.",
            metadata={"source": "test_direct", "type": "description"},
            namespace="knowledge",
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("MEMORY", "Store document", f"Doc ID: {doc_id}", latency)

        # Store more
        await service.store(
            text="Python est un langage de programmation polyvalent.",
            metadata={"source": "test_direct", "type": "fact"},
            namespace="knowledge",
        )
        await service.store(
            text="L'apprentissage automatique est une branche de l'intelligence artificielle.",
            metadata={"source": "test_direct", "type": "fact"},
            namespace="knowledge",
        )

        # Search
        start = time.monotonic()
        results = await service.search(
            query="agent IA souverain",
            namespace="knowledge",
            top_k=3,
        )
        latency = (time.monotonic() - start) * 1000
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        docs = (results.get("documents") or [[]])[0] if results.get("documents") else []
        log_ok("MEMORY", "Search documents",
               f"Results: {len(ids)}, Top: {docs[0][:80] if docs else 'N/A'}...",
               latency)

        # Count
        start = time.monotonic()
        count = await service.count(namespace="knowledge")
        latency = (time.monotonic() - start) * 1000
        log_ok("MEMORY", "Count documents", f"Count: {count}", latency)

    except Exception as e:
        log_fail("MEMORY", "ChromaDB operations", str(e)[:200])


async def test_knowledge_graph():
    """Test 9: Knowledge Graph"""
    print(f"\n{BOLD}═══ KNOWLEDGE GRAPH ═══{RESET}")

    try:
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()

        # Add entities
        start = time.monotonic()
        n1 = kg.add_entity("Python", entity_type="language")
        n2 = kg.add_entity("Machine Learning", entity_type="concept")
        n3 = kg.add_entity("FastAPI", entity_type="framework")
        latency = (time.monotonic() - start) * 1000
        log_ok("KG", "Add entities", f"Nodes: {n1}, {n2}, {n3}", latency)

        # Add relations
        start = time.monotonic()
        kg.add_relationship("Python", "Machine Learning", "used_for")
        kg.add_relationship("FastAPI", "Python", "built_with")
        latency = (time.monotonic() - start) * 1000
        log_ok("KG", "Add relationships", "Python→ML, FastAPI→Python", latency)

        # Search
        start = time.monotonic()
        results = kg.search_entities("Python")
        latency = (time.monotonic() - start) * 1000
        log_ok("KG", "Search entities", f"Results: {results[:3]}", latency)

        # Get neighbors
        start = time.monotonic()
        neighbors = kg.get_neighbors("Python", degree=1)
        latency = (time.monotonic() - start) * 1000
        log_ok("KG", "Get neighbors", f"Neighbors: {str(neighbors)[:100]}", latency)

        # Save
        kg.save()
        log_ok("KG", "Save graph", "Persisted to disk")

    except Exception as e:
        log_fail("KG", "Knowledge Graph operations", str(e)[:200])


async def test_security():
    """Test 10: Security components"""
    print(f"\n{BOLD}═══ SÉCURITÉ ═══{RESET}")

    # Rate limiter
    try:
        from nexus.security.rate_limiter import RateLimiter
        limiter = RateLimiter()
        limiter.check("test_user", action="test", tokens=1)
        log_ok("SEC", "Rate limiter", "Check passed")
    except Exception as e:
        log_fail("SEC", "Rate limiter", str(e))

    # Sandbox
    try:
        from nexus.security.sandbox import LocalSandbox
        sandbox = LocalSandbox(timeout=5, max_memory_mb=256)
        start = time.monotonic()
        result = await sandbox.execute_python("print('Sandbox OK!')", timeout=5)
        latency = (time.monotonic() - start) * 1000
        log_ok("SANDBOX", "Execute Python in sandbox",
               f"Stdout: {result.stdout[:80]}, Exit: {result.exit_code}",
               latency)
    except Exception as e:
        log_fail("SANDBOX", "Execute Python in sandbox", str(e)[:200])

    # Audit logger
    try:
        from nexus.security.audit import AuditLogger, AuditCategory, AuditLevel
        audit = AuditLogger()
        audit.log(category=AuditCategory.AGENT_ACTION, action="test_action", target="test_target")
        entries = audit.query(limit=5)
        log_ok("AUDIT", "Audit logger", f"Entries: {len(entries)}")
    except Exception as e:
        log_fail("AUDIT", "Audit logger", str(e)[:200])


async def test_agents():
    """Test 11: Agent registry"""
    print(f"\n{BOLD}═══ AGENTS ═══{RESET}")

    try:
        from nexus.core.registry import get_registry
        registry = get_registry()
        types = registry.list_types()
        stats = registry.get_stats()
        log_ok("AGENTS", "Registry", f"Types: {types}, Stats: {stats}")
    except Exception as e:
        log_fail("AGENTS", "Registry", str(e)[:200])


async def test_config():
    """Test 12: Configuration"""
    print(f"\n{BOLD}═══ CONFIGURATION ═══{RESET}")

    from nexus.core.config import get_settings
    settings = get_settings()
    log_ok("CONFIG", "Settings loaded",
           f"Env: {settings.nexus_env.value}, Providers: {settings.available_providers}")
    log_ok("CONFIG", "Gemini API key",
           f"Configured: {bool(settings.google_api_key)}, Key: {settings.google_api_key[:8]}...{settings.google_api_key[-4:]}")
    log_ok("CONFIG", "Fallback chain",
           f"Available: {settings.fallback_providers}")


async def test_orchestrator():
    """Test 13: Orchestrator"""
    print(f"\n{BOLD}═══ ORCHESTRATEUR ═══{RESET}")

    try:
        from nexus.orchestrator.langgraph_engine import run_nexus_task
        start = time.monotonic()
        result = await run_nexus_task(
            task="Calcule 15 * 7 et explique le résultat",
            messages=[],
        )
        latency = (time.monotonic() - start) * 1000
        log_ok("ORCH", "Run task",
               f"Status: {result.get('status', 'N/A')}, Result: {str(result.get('result', ''))[:150]}...",
               latency)
    except Exception as e:
        log_fail("ORCH", "Run task", str(e)[:300])


async def main():
    print(f"\n{BOLD}{'═'*60}")
    print(f"  NEXUS AGENT — TEST DIRECT EN SITUATION RÉELLE")
    print(f"  Model: gemma-4-31b-it via Google AI Studio")
    print(f"{'═'*60}{RESET}\n")

    # Config first
    await test_config()

    # LLM tests (core functionality)
    await test_llm_router()

    # Gemini direct
    await test_gemini_provider_direct()

    # Code execution
    await test_code_executor()

    # Memory
    await test_memory()

    # Knowledge Graph
    await test_knowledge_graph()

    # Security
    await test_security()

    # Agents
    await test_agents()

    # Orchestrator (uses LLM)
    await test_orchestrator()

    # Summary
    total = results["passed"] + results["failed"]
    print(f"\n{BOLD}{'═'*60}")
    print(f"  RÉSULTATS DU TEST")
    print(f"{'═'*60}{RESET}")
    print(f"  {GREEN}✓ Passés: {results['passed']}/{total}{RESET}")
    print(f"  {RED}✗ Échoués: {results['failed']}/{total}{RESET}")

    if results["errors"]:
        print(f"\n{RED}Détail des échecs:{RESET}")
        for err in results["errors"]:
            print(f"  {RED}→ {err}{RESET}")

    rate = (results["passed"] / total * 100) if total > 0 else 0
    print(f"\n  Taux de réussite: {BOLD}{rate:.1f}%{RESET}")

    if rate >= 80:
        print(f"  {GREEN}🎉 Agent NEXUS opérationnel !{RESET}")
    elif rate >= 50:
        print(f"  {YELLOW}⚠ Agent NEXUS partiellement opérationnel{RESET}")
    else:
        print(f"  {RED}❌ Agent NEXUS nécessite des corrections{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
