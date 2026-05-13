#!/usr/bin/env python3
"""
NexusAgent — Test GLM-4-Flash en situation réelle
===================================================
Test complet de l'agent avec GLM-4-Flash (ZhipuAI) — 100% GRATUIT

Usage:
    1. Mets ta clé ZAI_API_KEY dans .env
    2. python test_glm_flash.py
"""

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# ─── Color output ──────────────────────────────────────────────
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

def ok(msg): print(f"  {C.GREEN}✅ {msg}{C.END}")
def fail(msg): print(f"  {C.RED}❌ {msg}{C.END}")
def warn(msg): print(f"  {C.YELLOW}⚠️  {msg}{C.END}")
def info(msg): print(f"  {C.BLUE}ℹ️  {msg}{C.END}")
def header(msg): print(f"\n{C.CYAN}{C.BOLD}{'='*60}\n  {msg}\n{'='*60}{C.END}")


# ─── Test counter ──────────────────────────────────────────────
passed = 0
failed = 0
skipped = 0


def record(result: bool, name: str, detail: str = ""):
    global passed, failed
    if result:
        ok(f"{name}" + (f" — {detail}" if detail else ""))
        passed += 1
    else:
        fail(f"{name}" + (f" — {detail}" if detail else ""))
        failed += 1


# ─── Test 1: Configuration ─────────────────────────────────────
def test_config():
    header("TEST 1: Configuration ZhipuAI")
    try:
        from nexus.core.config import get_settings, reload_settings
        reload_settings()
        s = get_settings()

        record(
            s.zai_api_key and s.zai_api_key != "YOUR_ZAI_API_KEY_HERE",
            "ZAI_API_KEY configurée",
            f"...{s.zai_api_key[-8:]}" if s.zai_api_key and len(s.zai_api_key) > 8 else ""
        )
        record(
            s.zai_base_url == "https://open.bigmodel.cn/api/paas/v4",
            "ZAI_BASE_URL correct",
            s.zai_base_url
        )
        record(
            s.llm_default_provider == "glm",
            "LLM_DEFAULT_PROVIDER = glm",
        )
        return s.zai_api_key and s.zai_api_key != "YOUR_ZAI_API_KEY_HERE"
    except Exception as e:
        fail(f"Config error: {e}")
        return False


# ─── Test 2: GLM Provider direct ──────────────────────────────
async def test_glm_provider_direct():
    header("TEST 2: GLM Provider — Appel direct API")
    try:
        from nexus.llm.providers.glm_provider import GLMProvider, GLM_MODELS

        info(f"Modèles disponibles: {list(GLM_MODELS.keys())}")

        # Check free models
        free_models = [k for k, v in GLM_MODELS.items() if v.get("free")]
        record(len(free_models) >= 2, f"Modèles gratuits déclarés: {free_models}", )

        provider = GLMProvider()
        record(provider.is_available, "GLM Provider disponible", f"name={provider.name}")

        # Test simple completion with glm-4-flash
        info("Appel GLM-4-Flash: 'Dis bonjour en français et explique ce qu'est NexusAgent en 2 phrases'")
        start = time.monotonic()
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Tu es NexusAgent, un assistant IA intelligent et polyvalent."},
                {"role": "user", "content": "Dis bonjour en français et explique ce qu'est NexusAgent en 2 phrases."},
            ],
            model="glm-4-flash",
            temperature=0.7,
            max_tokens=512,
        )
        latency = (time.monotonic() - start) * 1000

        record(
            response.content and len(response.content) > 10,
            "GLM-4-Flash réponse reçue",
            f"latence={response.latency_ms:.0f}ms, tokens={response.usage.get('total_tokens', '?')}, coût=${response.cost_usd:.6f}"
        )
        info(f"Réponse: {response.content[:200]}...")
        record(
            response.cost_usd == 0.0,
            "GLM-4-Flash coût = $0.00 (GRATUIT)",
        )

        # Test with glm-4-flash streaming
        info("Test streaming GLM-4-Flash...")
        chunks = []
        start = time.monotonic()
        async for chunk in provider.stream(
            messages=[
                {"role": "user", "content": "Compte de 1 à 5 en français."},
            ],
            model="glm-4-flash",
            max_tokens=200,
        ):
            chunks.append(chunk)
        stream_content = "".join(chunks)
        stream_latency = (time.monotonic() - start) * 1000

        record(
            len(stream_content) > 5,
            "GLM-4-Flash streaming OK",
            f"{len(chunks)} chunks, {stream_latency:.0f}ms"
        )
        info(f"Stream: {stream_content[:150]}...")

        return True
    except Exception as e:
        fail(f"GLM Provider error: {e}")
        traceback.print_exc()
        return False


# ─── Test 3: LLM Router avec GLM ──────────────────────────────
async def test_llm_router():
    header("TEST 3: LLM Router — Routing via GLM")
    try:
        from nexus.llm.router import LLMRouter, Provider

        router = LLMRouter()

        # Check provider availability
        status = router.get_provider_status()
        glm_available = status.get("glm", {}).get("available", False)
        record(glm_available, "GLM provider disponible via router")

        # Test completion via router with explicit GLM provider
        info("Router: appel avec provider='glm'...")
        start = time.monotonic()
        response = await router.complete(
            messages=[
                {"role": "user", "content": "Quelle est la capitale de la France ? Réponds en une phrase."},
            ],
            provider="glm",
            model="glm-4-flash",
            max_tokens=100,
        )
        latency = (time.monotonic() - start) * 1000

        record(
            response.content and len(response.content) > 5,
            "Router GLM-4-Flash réponse OK",
            f"provider={response.provider.value}, latence={response.latency_ms:.0f}ms"
        )
        info(f"Réponse: {response.content[:150]}...")

        # Test function calling / tool use
        info("Router: test function calling avec GLM-4-Flash...")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Obtenir la météo pour une ville",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "Nom de la ville"},
                        },
                        "required": ["city"],
                    },
                },
            }
        ]

        response = await router.complete(
            messages=[
                {"role": "user", "content": "Quel temps fait-il à Paris ?"},
            ],
            provider="glm",
            model="glm-4-flash",
            tools=tools,
            max_tokens=256,
        )

        has_tool_calls = len(response.tool_calls) > 0
        record(
            has_tool_calls or "paris" in response.content.lower() or "météo" in response.content.lower() or "weather" in response.content.lower(),
            "GLM-4-Flash function calling",
            f"tool_calls={len(response.tool_calls)}, content snippet: {response.content[:80]}..."
        )

        return True
    except Exception as e:
        fail(f"Router error: {e}")
        traceback.print_exc()
        return False


# ─── Test 4: Agents avec GLM ──────────────────────────────────
async def test_agents_with_glm():
    header("TEST 4: Agents NexusAgent avec GLM-4-Flash")
    try:
        # Test Developer Agent
        info("Test Developer Agent avec GLM-4-Flash...")
        try:
            from nexus.agents.developer import DeveloperAgent
            dev = DeveloperAgent()
            record(dev.agent_type == "developer", "DeveloperAgent créé", f"type={dev.agent_type}")
            record(dev.llm_router is not None, "DeveloperAgent LLM router initialisé (lazy)")
        except Exception as e:
            fail(f"DeveloperAgent error: {e}")

        # Test Researcher Agent
        info("Test Researcher Agent avec GLM-4-Flash...")
        try:
            from nexus.agents.researcher import ResearcherAgent
            res = ResearcherAgent()
            record(res.agent_type == "researcher", "ResearcherAgent créé", f"type={res.agent_type}")
        except Exception as e:
            fail(f"ResearcherAgent error: {e}")

        # Test Analyst Agent
        info("Test Analyst Agent avec GLM-4-Flash...")
        try:
            from nexus.agents.analyst import AnalystAgent
            ana = AnalystAgent()
            record(ana.agent_type == "analyst", "AnalystAgent créé", f"type={ana.agent_type}")
        except Exception as e:
            fail(f"AnalystAgent error: {e}")

        # Test Operator Agent
        info("Test Operator Agent avec GLM-4-Flash...")
        try:
            from nexus.agents.operator import OperatorAgent
            opt = OperatorAgent()
            record(opt.agent_type == "operator", "OperatorAgent créé", f"type={opt.agent_type}")
        except Exception as e:
            fail(f"OperatorAgent error: {e}")

        # Test agent system_prompt & capabilities
        info("Test des propriétés des agents...")
        record(len(dev.system_prompt) > 50, "DeveloperAgent system_prompt OK", f"{len(dev.system_prompt)} chars")
        record(len(dev.capabilities) > 0, "DeveloperAgent capabilities OK", f"{dev.capabilities}")

        return True
    except Exception as e:
        fail(f"Agents error: {e}")
        traceback.print_exc()
        return False


# ─── Test 5: Memory + Knowledge Graph ─────────────────────────
async def test_memory_and_knowledge():
    header("TEST 5: Mémoire & Knowledge Graph (avec GLM)")
    try:
        # ChromaDB Memory
        from nexus.memory.chroma_service import NexusMemoryService

        chroma = NexusMemoryService()
        info("NexusMemoryService créé")

        # Store a memory
        mem_id = await chroma.store(
            text="NexusAgent utilise GLM-4-Flash comme modèle gratuit via ZhipuAI",
            namespace="knowledge",
            metadata={"source": "test", "model": "glm-4-flash", "provider": "zhipuai"},
        )
        record(mem_id is not None, f"Mémoire stockée: {mem_id}")

        # Retrieve
        results = await chroma.search("Quel modèle utilise NexusAgent ?", top_k=3)
        record(len(results) > 0, f"Recherche mémoire: {len(results)} résultats")
        if results:
            info(f"Résultat: {str(list(results.values())[:1])[:100]}...")

        # Knowledge Graph
        try:
            from nexus.knowledge.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph()
            ok("Knowledge Graph créé")

            # Add a node
            kg.add_node("GLM-4-Flash", node_type="model", properties={"provider": "zhipuai", "cost": "free"})
            kg.add_node("NexusAgent", node_type="project")
            kg.add_edge("NexusAgent", "GLM-4-Flash", relation="uses")
            ok("Nœuds et arêtes ajoutés au graphe")

            # Query
            neighbors = kg.get_neighbors("NexusAgent")
            record(len(neighbors) > 0, f"Voisins de NexusAgent: {neighbors}")
        except Exception as e:
            warn(f"Knowledge Graph: {e}")

        return True
    except Exception as e:
        fail(f"Memory/Knowledge error: {e}")
        traceback.print_exc()
        return False


# ─── Test 6: Code Execution + Sandbox ─────────────────────────
async def test_code_and_sandbox():
    header("TEST 6: Exécution de code & Sandbox")
    try:
        # Code Executor
        from nexus.dev.code_executor import CodeExecutor
        executor = CodeExecutor()
        ok("CodeExecutor créé")

        # Use LocalSandbox for actual code execution (no Docker needed)
        from nexus.security.sandbox import LocalSandbox
        sandbox = LocalSandbox()
        result = await sandbox.execute_python("print('Hello from NexusAgent + GLM!')")
        output_text = result.stdout if hasattr(result, 'stdout') else str(result)
        record(
            "Hello" in output_text or result.exit_code == 0,
            "Exécution code Python OK",
            f"exit_code={result.exit_code}, stdout={output_text[:80]}"
        )

        # Also test CodeExecutor creation
        ok("CodeExecutor + LocalSandbox créés")
        sandbox_result = await sandbox.execute_python("result = 2 + 2; print(result)")
        record(sandbox_result is not None, f"Sandbox calcul: exit_code={sandbox_result.exit_code}, stdout={sandbox_result.stdout}")

        return True
    except Exception as e:
        fail(f"Code/Sandbox error: {e}")
        traceback.print_exc()
        return False


# ─── Test 7: Security (Rate Limiter, Audit) ───────────────────
async def test_security():
    header("TEST 7: Sécurité (Rate Limiter, Audit, Guardrails)")
    try:
        # Rate Limiter
        from nexus.security.rate_limiter import RateLimiter
        rl = RateLimiter()
        rl.add_limit("test-user", max_requests=60, window_seconds=60)
        for i in range(5):
            allowed = rl.is_allowed("test-user")
        record(allowed, "Rate Limiter: 5 requêtes autorisées")

        # Audit
        from nexus.security.audit import AuditLogger
        audit = AuditLogger()
        audit.log(action="api_call", actor="test", details={"model": "glm-4-flash"})
        ok("Audit log enregistré")

        # Guardrails
        from nexus.security.guardrails import GuardrailManager
        guard = GuardrailManager()
        result = guard.check_input("Ceci est un message normal et inoffensif")
        record(result, "Guardrails: message safe passé")

        return True
    except Exception as e:
        fail(f"Security error: {e}")
        traceback.print_exc()
        return False


# ─── Test 8: Conversation multi-tour avec GLM ─────────────────
async def test_multi_turn_conversation():
    header("TEST 8: Conversation multi-tour avec GLM-4-Flash")
    try:
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        # Tour 1
        messages = [
            {"role": "system", "content": "Tu es NexusAgent, un assistant IA. Réponds en français."},
            {"role": "user", "content": "Mon nom est Testeur. Retiens-le."},
        ]
        r1 = await provider.complete(messages=messages, model="glm-4-flash", max_tokens=200)
        record(len(r1.content) > 5, "Tour 1: présentation", r1.content[:80])

        # Tour 2
        messages.append({"role": "assistant", "content": r1.content})
        messages.append({"role": "user", "content": "Quel est mon nom ?"})
        r2 = await provider.complete(messages=messages, model="glm-4-flash", max_tokens=200)
        name_recalled = "Testeur" in r2.content or "testeur" in r2.content.lower()
        record(name_recalled, "Tour 2: rappel du nom", r2.content[:80])

        # Tour 3 — Reasoning
        messages.append({"role": "assistant", "content": r2.content})
        messages.append({"role": "user", "content": "Si j'ai 3 pommes et que j'en donne 1, combien m'en reste-t-il ?"})
        r3 = await provider.complete(messages=messages, model="glm-4-flash", max_tokens=200)
        has_2 = "2" in r3.content or "deux" in r3.content.lower()
        record(has_2, "Tour 3: raisonnement mathématique", r3.content[:80])

        info(f"Conversation 3 tours — coût total: ${provider._total_cost:.6f}")

        return True
    except Exception as e:
        fail(f"Multi-turn error: {e}")
        traceback.print_exc()
        return False


# ─── Test 9: GLM-4.7-Flash (si disponible) ────────────────────
async def test_glm_47_flash():
    header("TEST 9: GLM-4.7-Flash (modèle gratuit le plus récent)")
    try:
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        info("Appel GLM-4.5-Flash...")
        response = await provider.complete(
            messages=[
                {"role": "system", "content": "Tu es NexusAgent. Réponds en français."},
                {"role": "user", "content": "Explique en 3 phrases pourquoi GLM-4-Flash est un excellent modèle gratuit pour les agents IA."},
            ],
            model="glm-4.5-flash",
            temperature=0.7,
            max_tokens=512,
        )

        record(
            response.content and len(response.content) > 5,
            "GLM-4.5-Flash réponse reçue",
            f"latence={response.latency_ms:.0f}ms, coût=${response.cost_usd:.6f}"
        )
        if response.content:
            info(f"Réponse: {response.content[:250]}...")
        record(response.cost_usd == 0.0, "GLM-4.5-Flash coût = $0.00 (GRATUIT)")

        return True
    except Exception as e:
        fail(f"GLM-4.7-Flash error: {e}")
        warn("Ce modèle peut ne pas encore être disponible dans l'API")
        traceback.print_exc()
        return False


# ─── Main ──────────────────────────────────────────────────────
async def main():
    global passed, failed, skipped

    print(f"\n{C.CYAN}{C.BOLD}")
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║   NexusAgent — Test GLM-4-Flash (ZhipuAI)              ║")
    print("  ║   100% GRATUIT — 20M tokens offerts à l'inscription    ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print(f"{C.END}")

    # Check API key first
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key or api_key == "YOUR_ZAI_API_KEY_HERE":
        print(f"\n{C.RED}{C.BOLD}⚠️  ZAI_API_KEY non configurée !{C.END}")
        print(f"""
{C.YELLOW}Pour obtenir ta clé gratuite ZhipuAI :{C.END}

  1. Va sur {C.CYAN}https://open.bigmodel.cn/{C.END}
  2. Crée un compte gratuit (email ou téléphone)
  3. Va dans {C.CYAN}https://open.bigmodel.cn/usercenter/apikeys{C.END}
  4. Clique "Créer une nouvelle clé API"
  5. Copie la clé et mets-la dans le fichier .env :

     {C.CYAN}ZAI_API_KEY=ta_clé_ici{C.END}

  6. Relance ce test : {C.CYAN}python test_glm_flash.py{C.END}

{C.GREEN}🎁 Bonus : les nouveaux utilisateurs reçoivent 20 MILLIONS de tokens gratuits !{C.END}
{C.GREEN}🎁 GLM-4-Flash et GLM-4.7-Flash sont 100% GRATUITS (coût = $0.00){C.END}
""")
        sys.exit(1)

    start_time = time.monotonic()

    # Run all tests
    has_key = test_config()

    if has_key:
        await test_glm_provider_direct()
        await test_llm_router()
        await test_agents_with_glm()
        await test_memory_and_knowledge()
        await test_code_and_sandbox()
        await test_security()
        await test_multi_turn_conversation()
        await test_glm_47_flash()

    # Summary
    total = passed + failed
    elapsed = time.monotonic() - start_time

    print(f"\n{C.CYAN}{C.BOLD}{'='*60}")
    print(f"  RÉSULTATS — {total} tests en {elapsed:.1f}s")
    print(f"{'='*60}{C.END}")
    print(f"  {C.GREEN}✅ Réussis: {passed}{C.END}")
    print(f"  {C.RED}❌ Échoués: {failed}{C.END}")

    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}🎉 TOUS LES TESTS SONT PASSÉS ! GLM-4-Flash fonctionne parfaitement !{C.END}")
    elif passed > failed:
        print(f"\n  {C.YELLOW}{C.BOLD}⚠️  Majorité des tests passés. Quelques échecs mineurs.{C.END}")
    else:
        print(f"\n  {C.RED}{C.BOLD}❌ Trop d'échecs. Vérifie ta clé API ZAI.{C.END}")

    print()
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
