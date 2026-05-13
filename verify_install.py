"""
NEXUS — Installation Verification Script
Run this after setup_windows.bat to verify everything is working.

Usage:
    python verify_install.py
"""

import sys
import platform


def check_python():
    """Check Python version."""
    v = sys.version_info
    print(f"  Python: {v.major}.{v.minor}.{v.micro}")
    if v < (3, 11):
        print("  [FAIL] Python 3.11+ required!")
        return False
    print("  [OK] Python version OK")
    return True


def check_module(module_name, friendly_name=None):
    """Check if a module can be imported."""
    name = friendly_name or module_name
    try:
        mod = __import__(module_name)
        version = getattr(mod, "__version__", "unknown")
        print(f"  [OK] {name}: {version}")
        return True
    except ImportError as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def check_nexus_modules():
    """Check all NEXUS modules can be imported."""
    modules = [
        ("nexus.core.config", "Core Config"),
        ("nexus.core.exceptions", "Core Exceptions"),
        ("nexus.core.observability", "Observability"),
        ("nexus.core.registry", "Agent Registry"),
        ("nexus.core.a2a", "A2A Protocol"),
        ("nexus.memory.working", "Working Memory"),
        ("nexus.llm.router", "LLM Router"),
        ("nexus.llm.providers.openai_provider", "OpenAI Provider"),
        ("nexus.llm.providers.anthropic_provider", "Anthropic Provider"),
        ("nexus.llm.providers.gemini_provider", "Gemini Provider"),
        ("nexus.llm.providers.glm_provider", "GLM Provider"),
        ("nexus.llm.providers.ollama_provider", "Ollama Provider"),
        ("nexus.reasoning.react", "ReAct Reasoning"),
        ("nexus.reasoning.tot", "Tree-of-Thought"),
        ("nexus.reasoning.lats", "LATS Reasoning"),
        ("nexus.security.sandbox", "Sandbox"),
        ("nexus.security.audit", "Audit Logger"),
        ("nexus.security.guardrails", "Guardrails"),
        ("nexus.security.rate_limiter", "Rate Limiter"),
        ("nexus.security.secrets", "Secrets Manager"),
        ("nexus.knowledge.knowledge_graph", "Knowledge Graph"),
        ("nexus.knowledge.rag_pipeline", "RAG Pipeline"),
        ("nexus.knowledge.deep_research", "Deep Research"),
        ("nexus.knowledge.web_search", "Web Search"),
        ("nexus.dev.code_executor", "Code Executor"),
        ("nexus.dev.git_integration", "Git Integration"),
        ("nexus.comms.channels", "Channel System"),
        ("nexus.comms.voice_io", "Voice I/O"),
        ("nexus.computer.computer_use", "Computer Use"),
        ("nexus.api.puter_proxy", "Puter Proxy"),
        ("nexus.orchestrator.langgraph_engine", "LangGraph Engine"),
        ("nexus.orchestrator.crewai_engine", "CrewAI Engine"),
        ("nexus.orchestrator.adk_engine", "ADK Engine"),
        ("nexus.orchestrator.patterns", "Multi-Agent Patterns"),
        ("nexus.orchestrator.skill_lifecycle", "Skill Lifecycle"),
        ("nexus.agents.base", "Base Agent"),
        ("nexus.agents.researcher", "Researcher Agent"),
        ("nexus.agents.developer", "Developer Agent"),
        ("nexus.agents.analyst", "Analyst Agent"),
        ("nexus.agents.operator", "Operator Agent"),
        ("nexus.mcp_server", "MCP Server"),
    ]

    passed = 0
    failed = 0
    for mod_name, friendly in modules:
        if check_module(mod_name, friendly):
            passed += 1
        else:
            failed += 1

    return passed, failed


def main():
    print()
    print("=" * 60)
    print("  NEXUS — Installation Verification")
    print(f"  Platform: {platform.system()} {platform.release()}")
    print("=" * 60)
    print()

    # Python check
    print("[1/4] Python")
    py_ok = check_python()
    print()

    # Core dependencies
    print("[2/4] Core Dependencies")
    deps_ok = all([
        check_module("chromadb"),
        check_module("fastapi"),
        check_module("uvicorn"),
        check_module("httpx"),
        check_module("pydantic"),
        check_module("pydantic_settings"),
        check_module("litellm"),
        check_module("typer"),
        check_module("rich"),
        check_module("networkx"),
    ])
    print()

    # NEXUS modules
    print("[3/4] NEXUS Modules")
    mod_passed, mod_failed = check_nexus_modules()
    print(f"  Total: {mod_passed} passed, {mod_failed} failed")
    print()

    # Quick functional test
    print("[4/4] Functional Tests")
    try:
        from nexus.core.config import get_settings
        settings = get_settings()
        print(f"  [OK] Config loaded (env={settings.nexus_env.value}, port={settings.nexus_port})")
        providers = settings.available_providers
        print(f"  [OK] Available providers: {', '.join(providers) or 'none'}")
    except Exception as e:
        print(f"  [FAIL] Config load: {e}")

    try:
        from nexus.memory.working import WorkingMemory, MessageRole
        wm = WorkingMemory(max_tokens=1000)
        wm.add(MessageRole.USER, "test")
        msgs = wm.get_messages()
        print(f"  [OK] Working Memory (messages={len(msgs)})")
    except Exception as e:
        print(f"  [FAIL] Working Memory: {e}")

    try:
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_entity("Test", entity_type="test")
        entity = kg.get_entity("Test")
        print(f"  [OK] Knowledge Graph (entity={entity is not None})")
    except Exception as e:
        print(f"  [FAIL] Knowledge Graph: {e}")

    try:
        from nexus.security.guardrails import GuardrailManager
        mgr = GuardrailManager()
        result = mgr.check_input("Hello, how are you?")
        print(f"  [OK] Guardrails (passed={result.passed})")
    except Exception as e:
        print(f"  [FAIL] Guardrails: {e}")

    print()
    print("=" * 60)
    print("  Verification complete!")
    print("=" * 60)
    print()

    if platform.system() == "Windows":
        print("  Windows Tips:")
        print("  - Run 'nexus serve' to start the API server")
        print("  - Run 'nexus chat' for interactive chat")
        print("  - Run 'python -m nexus.desktop.app' for the desktop GUI")
        print("  - Edit .env to add your API keys")
        print()


if __name__ == "__main__":
    main()
