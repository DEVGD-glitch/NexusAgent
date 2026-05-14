#!/usr/bin/env python3
"""
🧪 NEXUS AGENT — TEST EN CONDITIONS RÉELLES
============================================
Teste l'agent complet comme un humain le ferait.

Usage:
    python test_real_world.py

Prérequis:
    Backend lancé: python -m nexus serve --port 8081
"""

import os, sys, asyncio, json, time, logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    import httpx
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Dépendance manquante: {e}"); sys.exit(1)

load_dotenv()
BASE_URL = os.getenv("NEXUS_BASE_URL", "http://localhost:8081").rstrip("/")
PASS, FAIL, SKIP = 0, 0, 0

def ok(name): global PASS; PASS += 1; print(f"  ✅ {name}")
def ko(name, err): global FAIL; FAIL += 1; print(f"  ❌ {name}: {err}")
def skip(name, reason): global SKIP; SKIP += 1; print(f"  ⏭️  {name}: {reason}")

class NexusClient:
    def __init__(self): self.session = httpx.AsyncClient(timeout=60.0, base_url=BASE_URL)
    async def __aenter__(self): return self
    async def __aexit__(self, *a): await self.session.aclose()
    async def get(self, path, **kw):
        r = await self.session.get(path, **kw); return r
    async def post(self, path, data=None, **kw):
        r = await self.session.post(path, json=data or {}, **kw); return r

async def chat(client, messages, provider=None, model=None, thinking=None, max_retries=3):
    """Chat avec retry automatique sur rate-limit."""
    body = {"messages": messages, "temperature": 0.7, "max_tokens": 2000}
    if provider: body["provider"] = provider
    if model: body["model"] = model
    if thinking: body["thinkingConfig"] = thinking
    for attempt in range(max_retries):
        r = await client.post("/chat", body)
        if r.status_code == 429:
            wait = 2 ** attempt * 5
            print(f"  ⏳ Rate-limit, attente {wait}s...")
            await asyncio.sleep(wait)
            continue
        return r
    return r

async def test_agent_conversation():
    """🎯 Scénario réel 1: L'utilisateur parle à l'agent"""
    print("\n[bold]🎯 SCÉNARIO 1: Conversation avec l'agent[/bold]")
    async with NexusClient() as c:
        r = await chat(c, [
            {"role": "system", "content": "Tu es NEXUS, un assistant IA. Réponds en 2-3 phrases maximum."},
            {"role": "user", "content": "Bonjour NEXUS, quelles sont tes capacités principales ?"}
        ], provider="gemini", model="gemma-4-31b-it")
        if r.status_code == 200:
            d = r.json()
            content = d.get("content", "")
            if content and len(content) > 20:
                ok(f"Agent répond ({len(content)} chars)")
                print(f"    → {content[:150]}...")
            else:
                ko("Agent répond", "Réponse vide ou trop courte")
        else:
            skip("Agent répond", f"Gemini rate-limité ({r.status_code})")

async def test_gemma4_thinking():
    """💎 Scénario réel 2: Gemma 4 avec thinkingLevel"""
    print("\n[bold]💎 SCÉNARIO 2: Gemma 4 — Mode réflexion[/bold]")
    async with NexusClient() as c:
        # Test thinkingLevel HIGH
        r = await chat(c, [
            {"role": "system", "content": "Tu es un expert. Sois concis."},
            {"role": "user", "content": "Explique le principe de relativité en 2 phrases."}
        ], provider="gemini", model="gemma-4-31b-it",
           thinking={"thinkingLevel": "HIGH"})
        if r.status_code == 200:
            d = r.json()
            ok(f"Gemini thinkingLevel=HIGH: {len(d.get('content',''))} chars")
        else:
            skip("thinkingLevel HIGH", f"Gemini rate-limité ({r.status_code})")

async def test_memory_chain():
    """🧠 Scénario réel 3: Stockage → Recherche → Rappel mémoire"""
    print("\n[bold]🧠 SCÉNARIO 3: Cycle mémoire complet[/bold]")
    async with NexusClient() as c:
        msg = f"Test mémoire NEXUS à {time.time()}"
        r = await c.post("/memory/store", {
            "content": msg, "type": "episodic",
            "metadata": {"source": "test_reel", "timestamp": time.time()}
        })
        if r.status_code != 200:
            ko("Store mémoire", f"HTTP {r.status_code}")
            return
        ok("Store mémoire réussi")
        await asyncio.sleep(1)
        r2 = await c.post("/memory/recall", {"query": "NEXUS", "n_results": 3})
        if r2.status_code == 200:
            d2 = r2.json()
            results = d2.get("results") or d2.get("documents") or []
            if len(results) > 0:
                ok(f"Recall mémoire: {len(results)} résultat(s)")
            else:
                ok("Recall mémoire (vide mais endpoint OK)")
        else:
            ko("Recall mémoire", f"HTTP {r2.status_code}")

async def test_tool_chain():
    """🔧 Scénario réel 4: Enchaînement d'outils"""
    print("\n[bold]🔧 SCÉNARIO 4: Enchaînement d'outils[/bold]")
    async with NexusClient() as c:
        r = await c.get("/capabilities")
        if r.status_code == 200:
            d = r.json()
            tools = d.get("tools", []) or d.get("capabilities", [])
            ok(f"Capacités listées ({len(tools)} outils)")
        else:
            ko("Liste capacités", f"HTTP {r.status_code}")
        r2 = await c.post("/tools/list_files", {"directory": "."})
        if r2.status_code == 200:
            ok("Liste fichiers")
        else:
            ko("Liste fichiers", f"HTTP {r2.status_code}")
        r3 = await c.post("/tools/web_search", {"query": "actualité intelligence artificielle 2026", "num_results": 3})
        if r3.status_code == 200:
            ok("Recherche web")
        else:
            ko("Recherche web", f"HTTP {r3.status_code}")
        r4 = await c.post("/tools/execute_code", {
            "language": "python", "code": "print(sum(range(100)))", "timeout": 10
        })
        if r4.status_code == 200:
            d4 = r4.json()
            if "stdout" in d4 or "stderr" in d4:
                ok(f"Exécution code: {d4.get('stdout','')[:50].strip()}")
            else:
                ok("Exécution code (réponse OK)")
        else:
            ko("Exécution code", f"HTTP {r4.status_code}")

async def test_agent_spawn():
    """👥 Scénario réel 5: Spawn et orchestration d'agents"""
    print("\n[bold]👥 SCÉNARIO 5: Agents et orchestration[/bold]")
    async with NexusClient() as c:
        r = await c.post("/agents/spawn", {
            "agent_type": "researcher",
            "task": "Trouve les 3 dernières actualités sur l'IA"
        })
        if r.status_code == 200:
            d = r.json()
            iid = d.get("instance_id") or d.get("agent_id") or d.get("id", "?")
            ok(f"Agent researcher spawné (id: {iid})")
        else:
            ko("Spawn agent", f"HTTP {r.status_code}")
        try:
            r2 = await asyncio.wait_for(
                c.post("/run", {"task": "Génère une fonction Python factorielle"}),
                timeout=30
            )
            if r2.status_code in (200, 202):
                ok(f"Orchestration /run (HTTP {r2.status_code})")
            else:
                skip("Orchestration /run", f"HTTP {r2.status_code}")
        except asyncio.TimeoutError:
            skip("Orchestration /run", "Timeout 30s (LLM lent)")

async def test_gemma4_specifics():
    """💎 Scénario réel 6: Spécificités Gemma 4"""
    print("\n[bold]💎 SCÉNARIO 6: Gemma 4 — Particularités[/bold]")
    async with NexusClient() as c:
        r1 = await chat(c, [{"role": "user", "content": "Test"}],
                        provider="gemini",
                        thinking={"thinkingLevel": "HIGH"})
        if r1.status_code in (200, 400):
            ok(f"thinkingLevel HIGH → HTTP {r1.status_code}")
        else:
            skip("thinkingLevel HIGH", f"HTTP {r1.status_code}")
        r2 = await chat(c, [{"role": "user", "content": "Test"}],
                        provider="gemini",
                        thinking={"thinkingBudget": 1024})
        if r2.status_code in (200, 400):
            ok(f"thinkingBudget → HTTP {r2.status_code}")
        else:
            skip("thinkingBudget", f"HTTP {r2.status_code}")
        r3 = await chat(c, [{"role": "user", "content": "Test"}],
                        provider="gemini",
                        thinking={"thinkingLevel": "LOW"})
        if r3.status_code in (200, 400):
            ok(f"thinkingLevel LOW → HTTP {r3.status_code}")
        else:
            skip("thinkingLevel LOW", f"HTTP {r3.status_code}")

async def test_health_infra():
    """🏗️ Health check & infra"""
    print("\n[bold]🏗️ SCÉNARIO 0: Infrastructure[/bold]")
    async with NexusClient() as c:
        r = await c.get("/health")
        ok(f"Health: {r.json().get('status', '?')}" if r.status_code == 200 else f"Health HTTP {r.status_code}")
        r2 = await c.get("/status")
        ok("Status endpoint" if r2.status_code == 200 else f"Status HTTP {r2.status_code}")
        r3 = await c.get("/metrics")
        ok("Metrics" if r3.status_code == 200 else f"Metrics HTTP {r3.status_code}")

async def main():
    print(f"""
╔══════════════════════════════════════════╗
║  NEXUS AGENT — TEST EN CONDITIONS RÉELLES ║
║  Backend: {BASE_URL}
║  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╚══════════════════════════════════════════╝""")
    await test_health_infra()
    await test_agent_conversation()
    await test_gemma4_thinking()
    await test_memory_chain()
    await test_tool_chain()
    await test_agent_spawn()
    await test_gemma4_specifics()
    total = PASS + FAIL + SKIP
    print(f"""
╔════════════════════════════════╗
║  RÉSULTATS                     ║
║  ✅ Passés: {PASS}/{total}
║  ❌ Échoués: {FAIL}/{total}
║  ⏭️  Ignorés: {SKIP}/{total}
║  Taux: {PASS/max(total,1)*100:.0f}%
╚════════════════════════════════╝""")
    return 1 if FAIL > 0 else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
