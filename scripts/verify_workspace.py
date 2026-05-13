#!/usr/bin/env python3
"""
NEXUS Workspace Verification Script.

Verifies that all required components are present and functional.
Run this before starting development.
"""

import sys
from pathlib import Path

# Add workspace to Python path
BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

# Required directories
REQUIRED_DIRS = [
    "nexus/core",
    "nexus/orchestrator",
    "nexus/reasoning",
    "nexus/memory",
    "nexus/agents",
    "nexus/llm/providers",
    "nexus/browser",
    "nexus/computer",
    "nexus/dev",
    "nexus/knowledge",
    "nexus/comms",
    "nexus/security",
    "nexus/api",
    "nexus/cli",
    "tests/core",
    "tests/memory",
    "tests/gateway",
    "docker",
]

# Required Python files
REQUIRED_FILES = [
    "pyproject.toml",
    ".env.example",
    "docker-compose.yml",
    "nexus/core/config.py",
    "nexus/core/exceptions.py",
    "nexus/core/gateway.py",
    "nexus/memory/chroma_service.py",
    "nexus/memory/working.py",
    "nexus/memory/episodic.py",
    "nexus/memory/semantic.py",
    "nexus/memory/procedural.py",
    "nexus/memory/identity.py",
    "nexus/llm/router.py",
    "nexus/orchestrator/langgraph_engine.py",
    "nexus/reasoning/react.py",
    "nexus/reasoning/selector.py",
    "nexus/mcp_server.py",
    "nexus/cli/__init__.py",
    "docker/Dockerfile.core",
    "docker/Dockerfile.browser",
    "docker/browser_service.py",
]

# Core packages that should be importable
CORE_PACKAGES = [
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("fastapi", "fastapi"),
    ("chromadb", "chromadb"),
    ("mcp", "mcp"),
    ("langgraph", "langgraph"),
    ("litellm", "litellm"),
]


def main():
    errors = []

    print("=" * 60)
    print("  NEXUS Workspace Verification")
    print("=" * 60)

    # Check directories
    print("\n--- Directories ---")
    for dir_path in REQUIRED_DIRS:
        full_path = BASE / dir_path
        if full_path.exists():
            print(f"  OK  {dir_path}/")
        else:
            errors.append(f"MISSING DIR: {dir_path}/")
            print(f"  FAIL  {dir_path}/")

    # Check files
    print("\n--- Files ---")
    for file_path in REQUIRED_FILES:
        full_path = BASE / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"  OK  {file_path} ({size:,} bytes)")
        else:
            errors.append(f"MISSING FILE: {file_path}")
            print(f"  FAIL  {file_path}")

    # Check imports
    print("\n--- Packages ---")
    for module_name, display_name in CORE_PACKAGES:
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "unknown")
            print(f"  OK  {display_name} ({version})")
        except ImportError:
            errors.append(f"PACKAGE NOT INSTALLED: {display_name}")
            print(f"  FAIL  {display_name}")

    # Check config import
    print("\n--- NEXUS Modules ---")
    try:
        from nexus.core.config import NexusConfig, get_settings
        config = NexusConfig()
        print(f"  OK  nexus.core.config (env={config.nexus_env.value})")
    except Exception as e:
        errors.append(f"CONFIG IMPORT FAILED: {e}")
        print(f"  FAIL  nexus.core.config: {e}")

    try:
        from nexus.memory.chroma_service import NexusMemoryService
        print(f"  OK  nexus.memory.chroma_service")
    except Exception as e:
        errors.append(f"MEMORY IMPORT FAILED: {e}")
        print(f"  FAIL  nexus.memory.chroma_service: {e}")

    try:
        from nexus.llm.router import LLMRouter
        print(f"  OK  nexus.llm.router")
    except Exception as e:
        errors.append(f"LLM ROUTER IMPORT FAILED: {e}")
        print(f"  FAIL  nexus.llm.router: {e}")

    try:
        from nexus.mcp_server import nexus_mcp
        print(f"  OK  nexus.mcp_server")
    except Exception as e:
        errors.append(f"MCP SERVER IMPORT FAILED: {e}")
        print(f"  FAIL  nexus.mcp_server: {e}")

    try:
        from nexus.core.gateway import app
        print(f"  OK  nexus.core.gateway")
    except Exception as e:
        errors.append(f"GATEWAY IMPORT FAILED: {e}")
        print(f"  FAIL  nexus.core.gateway: {e}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"  RESULT: {len(errors)} ERROR(S)")
        for err in errors:
            print(f"    - {err}")
        sys.exit(1)
    else:
        print("  WORKSPACE 100% READY")
        print("  You can start NEXUS with: uvicorn nexus.core.gateway:app --port 8080")
        sys.exit(0)


if __name__ == "__main__":
    main()
