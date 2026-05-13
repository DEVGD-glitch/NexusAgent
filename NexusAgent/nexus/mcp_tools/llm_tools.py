"""
NEXUS MCP LLM Tools.
"""

import json
from typing import Any, Optional

from nexus.llm.router import LLMRouter, TaskComplexity


async def llm_complete(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Complete a prompt using the LLM router."""
    try:
        router = LLMRouter()
        response = await router.complete(
            messages=[{"role": "user", "content": prompt}],
            task_complexity=TaskComplexity.MEDIUM,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return json.dumps({
            "content": response.content,
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def llm_list_models() -> str:
    """List available LLM models."""
    try:
        router = LLMRouter()
        models = router.list_models()
        return json.dumps({"models": models})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def llm_provider_status() -> str:
    """Get status of all LLM providers."""
    try:
        router = LLMRouter()
        status = router.get_provider_status()
        return json.dumps({"providers": status})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def llm_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> str:
    """Stream a completion (returns first chunk)."""
    try:
        router = LLMRouter()
        response = await router.complete(
            messages=[{"role": "user", "content": prompt}],
            task_complexity=TaskComplexity.SIMPLE,
            temperature=temperature,
            stream=False,
        )
        return json.dumps({"content": response.content, "model": model})
    except Exception as e:
        return json.dumps({"error": str(e)})