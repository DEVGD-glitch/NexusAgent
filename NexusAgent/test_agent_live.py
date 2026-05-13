#!/usr/bin/env python3
"""
NEXUS Agent — Test en situation réelle avec Google AI Studio (gemma-4-31b-it)

Teste TOUTES les fonctionnalités de l'agent :
1. Chat completion (LLM direct)
2. Exécution de code
3. Mémoire vectorielle (ChromaDB)
4. Knowledge Graph
5. Raisonnement (ReAct, Tree-of-Thought)
6. Orchestration (Run task)
7. Outils MCP (search_memory, store_memory, etc.)
8. Sécurité (sandbox, audit)
9. Avatar (speak, expression)
10. WebSocket (events temps réel)
11. Status système
12. Web Search

Usage:
    GOOGLE_API_KEY=ta_cle python test_agent_live.py
"""

import asyncio
import json
import sys
import time
import os

# Ensure .env is loaded
from dotenv import load_dotenv
load_dotenv()

import httpx

BASE_URL = "http://localhost:8080"
TIMEOUT = 60.0

# Colors for terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

results = {"passed": 0, "failed": 0, "errors": []}


def log_test(category: str, name: str, status: str, detail: str = "", latency_ms: float = 0):
    icon = f"{GREEN}✓{RESET}" if status == "PASS" else f"{RED}✗{RESET}"
    lat_str = f" ({latency_ms:.0f}ms)" if latency_ms > 0 else ""
    print(f"  {icon} {CYAN}[{category}]{RESET} {name}{lat_str}")
    if detail:
        print(f"    {YELLOW}→ {detail}{RESET}")
    if status == "PASS":
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["errors"].append(f"[{category}] {name}: {detail}")


async def test_health(client: httpx.AsyncClient):
    """Test 1: Server health / status"""
    print(f"\n{BOLD}═══ 1. STATUS & HEALTH ═══{RESET}")
    try:
        r = await client.get("/status", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            log_test("STATUS", "Server status", "PASS", f"Agent: {data.get('agent', 'N/A')}, Env: {data.get('environment', 'N/A')}")
        else:
            log_test("STATUS", "Server status", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        # Try alternative status endpoint
        try:
            r = await client.post("/tools/get_status", json={}, timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                log_test("STATUS", "Server status", "PASS", f"Agent: {data.get('agent', 'N/A')}, Providers: {data.get('providers_configured', [])}")
            else:
                log_test("STATUS", "Server status", "FAIL", f"HTTP {r.status_code}")
        except Exception as e2:
            log_test("STATUS", "Server status", "FAIL", str(e)[:100])


async def test_chat(client: httpx.AsyncClient):
    """Test 2: Chat completion with gemma-4-31b-it"""
    print(f"\n{BOLD}═══ 2. CHAT COMPLETION (gemma-4-31b-it) ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/chat", json={
            "messages": [{"role": "user", "content": "Bonjour ! Dis-moi bonjour en français et explique brièvement ce que tu es."}],
            "provider": "gemini",
            "model": "gemma-4-31b-it",
            "temperature": 0.7,
            "max_tokens": 512,
        }, timeout=TIMEOUT)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", "")
            log_test("CHAT", "Basic chat (FR)", "PASS", f"Provider: {data.get('provider')}, Model: {data.get('model')}, Response: {content[:100]}...", latency_ms=latency)
        else:
            log_test("CHAT", "Basic chat (FR)", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("CHAT", "Basic chat (FR)", "FAIL", str(e)[:200])


async def test_chat_code(client: httpx.AsyncClient):
    """Test 3: Chat with code generation request"""
    print(f"\n{BOLD}═══ 3. CHAT — CODE GENERATION ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/chat", json={
            "messages": [{"role": "user", "content": "Écris une fonction Python qui calcule la suite de Fibonacci jusqu'à n. Donne uniquement le code."}],
            "provider": "gemini",
            "model": "gemma-4-31b-it",
            "temperature": 0.3,
            "max_tokens": 1024,
        }, timeout=TIMEOUT)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", "")
            has_code = "def " in content or "fibonacci" in content.lower()
            log_test("CHAT", "Code generation", "PASS" if has_code else "WARN", f"Code detected: {has_code}, Content: {content[:120]}...", latency_ms=latency)
        else:
            log_test("CHAT", "Code generation", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("CHAT", "Code generation", "FAIL", str(e)[:200])


async def test_chat_reasoning(client: httpx.AsyncClient):
    """Test 4: Chat with reasoning task"""
    print(f"\n{BOLD}═══ 4. CHAT — RAISONNEMENT ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/chat", json={
            "messages": [{"role": "user", "content": "Si j'ai 3 pommes, que j'en donne 1 à Marie et 1 à Pierre, combien m'en reste-t-il ? Explique ton raisonnement."}],
            "provider": "gemini",
            "model": "gemma-4-31b-it",
            "temperature": 0.1,
            "max_tokens": 512,
        }, timeout=TIMEOUT)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", "")
            has_correct = "1" in content
            log_test("CHAT", "Reasoning (math)", "PASS" if has_correct else "FAIL", f"Response: {content[:150]}...", latency_ms=latency)
        else:
            log_test("CHAT", "Reasoning (math)", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("CHAT", "Reasoning (math)", "FAIL", str(e)[:200])


async def test_execute_code(client: httpx.AsyncClient):
    """Test 5: Code execution"""
    print(f"\n{BOLD}═══ 5. CODE EXECUTION ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/execute_code", json={
            "code": "print('Hello from NEXUS!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')",
            "language": "python",
            "timeout": 10,
        }, timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            stdout = data.get("stdout", "")
            log_test("CODE", "Execute Python", "PASS", f"Output: {stdout[:100]}", latency_ms=latency)
        else:
            log_test("CODE", "Execute Python", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("CODE", "Execute Python", "FAIL", str(e)[:200])


async def test_execute_sandboxed(client: httpx.AsyncClient):
    """Test 6: Sandboxed code execution"""
    print(f"\n{BOLD}═══ 6. SANDBOX EXECUTION ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/execute_sandboxed", json={
            "code": "import os\nprint(os.getcwd())\nprint('Sandbox test OK')",
            "timeout": 10,
        }, timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("SANDBOX", "Sandboxed Python", "PASS", f"Output: {data.get('stdout', '')[:80]}", latency_ms=latency)
        else:
            log_test("SANDBOX", "Sandboxed Python", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("SANDBOX", "Sandboxed Python", "FAIL", str(e)[:200])


async def test_memory(client: httpx.AsyncClient):
    """Test 7: Memory operations (store + search)"""
    print(f"\n{BOLD}═══ 7. MÉMOIRE VECTORIELLE ═══{RESET}")

    # Store
    start = time.monotonic()
    try:
        r = await client.post("/tools/store_memory", json={
            "text": "NEXUS est un agent IA souverain capable de raisonner, coder, mémoriser et orchestrer des tâches complexes.",
            "namespace": "knowledge",
            "source": "test_live",
        }, timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("MEMORY", "Store document", "PASS", f"Doc ID: {data.get('doc_id', 'N/A')}, Namespace: {data.get('namespace')}", latency_ms=latency)
        else:
            log_test("MEMORY", "Store document", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("MEMORY", "Store document", "FAIL", str(e)[:200])

    # Search
    start = time.monotonic()
    try:
        r = await client.post("/tools/search_memory", json={
            "query": "agent IA souverain",
            "namespace": "knowledge",
            "top_k": 3,
        }, timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            count = len(data) if isinstance(data, list) else 0
            log_test("MEMORY", "Search documents", "PASS", f"Results: {count}", latency_ms=latency)
        else:
            log_test("MEMORY", "Search documents", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("MEMORY", "Search documents", "FAIL", str(e)[:200])

    # Memory stats
    start = time.monotonic()
    try:
        r = await client.get("/memory/stats", timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("MEMORY", "Memory stats", "PASS", f"Namespaces: {list(data.get('namespaces', {}).keys())}", latency_ms=latency)
        else:
            log_test("MEMORY", "Memory stats", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("MEMORY", "Memory stats", "FAIL", str(e)[:200])


async def test_knowledge_graph(client: httpx.AsyncClient):
    """Test 8: Knowledge Graph operations"""
    print(f"\n{BOLD}═══ 8. KNOWLEDGE GRAPH ═══{RESET}")

    # Add entity
    start = time.monotonic()
    try:
        r = await client.post("/tools/knowledge_add_entity", json={
            "name": "Python",
            "entity_type": "language",
        }, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("KG", "Add entity", "PASS", f"Node ID: {data.get('node_id', 'N/A')}", latency_ms=latency)
        else:
            log_test("KG", "Add entity", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("KG", "Add entity", "FAIL", str(e)[:200])

    # Search entities
    start = time.monotonic()
    try:
        r = await client.post("/tools/knowledge_search", json={
            "query": "Python",
        }, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("KG", "Search entities", "PASS", f"Results: {data if isinstance(data, list) else len(str(data))}", latency_ms=latency)
        else:
            log_test("KG", "Search entities", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("KG", "Search entities", "FAIL", str(e)[:200])


async def test_file_operations(client: httpx.AsyncClient):
    """Test 9: File system operations"""
    print(f"\n{BOLD}═══ 9. FILE SYSTEM ═══{RESET}")

    # Write file
    start = time.monotonic()
    try:
        r = await client.post("/tools/write_file", json={
            "path": "test_output.txt",
            "content": "Hello from NEXUS test! Timestamp: " + str(time.time()),
        }, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("FILE", "Write file", "PASS", f"Bytes: {data.get('bytes_written', 'N/A')}", latency_ms=latency)
        else:
            log_test("FILE", "Write file", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("FILE", "Write file", "FAIL", str(e)[:200])

    # Read file
    start = time.monotonic()
    try:
        r = await client.post("/tools/read_file", json={
            "path": "test_output.txt",
        }, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("FILE", "Read file", "PASS", f"Size: {data.get('size_bytes', 'N/A')} bytes", latency_ms=latency)
        else:
            log_test("FILE", "Read file", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("FILE", "Read file", "FAIL", str(e)[:200])

    # List files
    start = time.monotonic()
    try:
        r = await client.post("/tools/list_files", json={
            "directory": ".",
            "pattern": "*.txt",
        }, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("FILE", "List files", "PASS", f"Count: {data.get('count', 'N/A')}", latency_ms=latency)
        else:
            log_test("FILE", "List files", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("FILE", "List files", "FAIL", str(e)[:200])


async def test_audit(client: httpx.AsyncClient):
    """Test 10: Audit log"""
    print(f"\n{BOLD}═══ 10. AUDIT & SÉCURITÉ ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/audit_query", json={"limit": 10}, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("AUDIT", "Query audit log", "PASS", f"Entries: {data.get('count', 'N/A')}", latency_ms=latency)
        else:
            log_test("AUDIT", "Query audit log", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("AUDIT", "Query audit log", "FAIL", str(e)[:200])


async def test_agents(client: httpx.AsyncClient):
    """Test 11: Agent registry"""
    print(f"\n{BOLD}═══ 11. AGENTS ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/list_agents", json={}, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            agent_types = data.get("types", [])
            log_test("AGENTS", "List agent types", "PASS", f"Types: {agent_types}", latency_ms=latency)
        else:
            log_test("AGENTS", "List agent types", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("AGENTS", "List agent types", "FAIL", str(e)[:200])


async def test_avatar(client: httpx.AsyncClient):
    """Test 12: Avatar tools"""
    print(f"\n{BOLD}═══ 12. AVATAR ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/avatar_list_voices", json={}, timeout=15.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("AVATAR", "List voices", "PASS", f"Response: {str(data)[:100]}", latency_ms=latency)
        else:
            log_test("AVATAR", "List voices", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("AVATAR", "List voices", "FAIL", str(e)[:200])


async def test_web_search(client: httpx.AsyncClient):
    """Test 13: Web search"""
    print(f"\n{BOLD}═══ 13. WEB SEARCH ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/tools/web_search", json={
            "query": "NexusAgent AI 2025",
            "num_results": 3,
        }, timeout=30.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            results_list = data.get("results", [])
            log_test("SEARCH", "Web search", "PASS", f"Results: {len(results_list)}", latency_ms=latency)
        else:
            log_test("SEARCH", "Web search", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("SEARCH", "Web search", "FAIL", str(e)[:200])


async def test_run_task(client: httpx.AsyncClient):
    """Test 14: Run orchestrator task"""
    print(f"\n{BOLD}═══ 14. ORCHESTRATION (RUN TASK) ═══{RESET}")
    start = time.monotonic()
    try:
        r = await client.post("/run", json={
            "task": "Calcule 15 * 7 et explique le résultat",
            "provider": "gemini",
        }, timeout=120.0)
        latency = (time.monotonic() - start) * 1000
        if r.status_code == 200:
            data = r.json()
            log_test("ORCH", "Run task", "PASS", f"Status: {data.get('status')}, Steps: {data.get('steps', 'N/A')}", latency_ms=latency)
        else:
            log_test("ORCH", "Run task", "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", latency_ms=latency)
    except Exception as e:
        log_test("ORCH", "Run task", "FAIL", str(e)[:200])


async def test_chat_multi_turn(client: httpx.AsyncClient):
    """Test 15: Multi-turn conversation"""
    print(f"\n{BOLD}═══ 15. CONVERSATION MULTI-TOUR ═══{RESET}")
    messages = [
        {"role": "user", "content": "Mon nom est Alice. Retiens-le."},
    ]
    start = time.monotonic()
    try:
        r = await client.post("/chat", json={
            "messages": messages,
            "provider": "gemini",
            "model": "gemma-4-31b-it",
            "temperature": 0.3,
            "max_tokens": 256,
        }, timeout=TIMEOUT)
        latency1 = (time.monotonic() - start) * 1000
        if r.status_code != 200:
            log_test("CHAT", "Multi-turn (turn 1)", "FAIL", f"HTTP {r.status_code}")
            return
        data1 = r.json()
        log_test("CHAT", "Multi-turn (turn 1)", "PASS", f"Response: {data1.get('content', '')[:80]}...", latency_ms=latency1)

        # Turn 2 — ask for the name
        messages.append({"role": "assistant", "content": data1.get("content", "")})
        messages.append({"role": "user", "content": "Quel est mon nom ?"})

        start = time.monotonic()
        r2 = await client.post("/chat", json={
            "messages": messages,
            "provider": "gemini",
            "model": "gemma-4-31b-it",
            "temperature": 0.1,
            "max_tokens": 256,
        }, timeout=TIMEOUT)
        latency2 = (time.monotonic() - start) * 1000
        if r2.status_code == 200:
            data2 = r2.json()
            content2 = data2.get("content", "")
            has_name = "Alice" in content2
            log_test("CHAT", "Multi-turn (turn 2)", "PASS" if has_name else "WARN", f"Remembers name: {has_name}, Response: {content2[:80]}...", latency_ms=latency2)
        else:
            log_test("CHAT", "Multi-turn (turn 2)", "FAIL", f"HTTP {r2.status_code}")
    except Exception as e:
        log_test("CHAT", "Multi-turn", "FAIL", str(e)[:200])


async def main():
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "YOUR_GOOGLE_API_KEY":
        print(f"{RED}ERREUR: GOOGLE_API_KEY non configurée{RESET}")
        print(f"Utilise: GOOGLE_API_KEY=ta_cle python test_agent_live.py")
        print(f"Ou configure le fichier .env")
        sys.exit(1)

    print(f"\n{BOLD}{'═'*60}")
    print(f"  NEXUS AGENT — TEST EN SITUATION RÉELLE")
    print(f"  Model: gemma-4-31b-it via Google AI Studio")
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"{'═'*60}{RESET}\n")

    # Wait for server
    print(f"{YELLOW}Vérification du serveur NEXUS...{RESET}")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as check:
        try:
            r = await check.get("/status")
            if r.status_code == 200:
                print(f"{GREEN}Serveur NEXUS détecté sur {BASE_URL}{RESET}")
            else:
                print(f"{YELLOW}Réponse inattendue: HTTP {r.status_code}{RESET}")
        except Exception as e:
            print(f"{RED}Serveur NEXUS non disponible sur {BASE_URL}{RESET}")
            print(f"{YELLOW}Lance d'abord: cd NexusAgent && GOOGLE_API_KEY=ta_cle python -m uvicorn nexus.api.gateway:app --host 0.0.0.0 --port 8080{RESET}")
            sys.exit(1)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        await test_health(client)
        await test_chat(client)
        await test_chat_code(client)
        await test_chat_reasoning(client)
        await test_chat_multi_turn(client)
        await test_execute_code(client)
        await test_execute_sandboxed(client)
        await test_memory(client)
        await test_knowledge_graph(client)
        await test_file_operations(client)
        await test_audit(client)
        await test_agents(client)
        await test_avatar(client)
        await test_web_search(client)
        await test_run_task(client)

    # Summary
    print(f"\n{BOLD}{'═'*60}")
    print(f"  RÉSULTATS DU TEST")
    print(f"{'═'*60}{RESET}")
    total = results["passed"] + results["failed"]
    print(f"  {GREEN}✓ Passés: {results['passed']}/{total}{RESET}")
    print(f"  {RED}✗ Échoués: {results['failed']}/{total}{RESET}")

    if results["errors"]:
        print(f"\n{RED}Détail des échecs:{RESET}")
        for err in results["errors"]:
            print(f"  {RED}→ {err}{RESET}")

    success_rate = (results["passed"] / total * 100) if total > 0 else 0
    print(f"\n  Taux de réussite: {BOLD}{success_rate:.1f}%{RESET}")

    if success_rate >= 80:
        print(f"  {GREEN}Agent NEXUS opérationnel ! 🎉{RESET}")
    elif success_rate >= 50:
        print(f"  {YELLOW}Agent NEXUS partiellement opérationnel{RESET}")
    else:
        print(f"  {RED}Agent NEXUS nécessite des corrections{RESET}")

    return success_rate >= 50


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
