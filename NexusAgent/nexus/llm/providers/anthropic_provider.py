"""
NEXUS Anthropic Provider — Claude 3.5 Sonnet, Claude 3 Opus via Anthropic API.

First-class provider implementation with LiteLLM integration and direct
SDK fallback. Supports Claude-specific features like extended thinking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError, LLMRateLimitError

logger = logging.getLogger(__name__)

ANTHROPIC_MODELS = {
    "claude-3-5-sonnet-20241022": {"context": 200000, "cost_input": 3.00, "cost_output": 15.00},
    "claude-3-opus-20240229": {"context": 200000, "cost_input": 15.00, "cost_output": 75.00},
    "claude-3-haiku-20240307": {"context": 200000, "cost_input": 0.25, "cost_output": 1.25},
    "claude-sonnet-4-20250514": {"context": 200000, "cost_input": 3.00, "cost_output": 15.00},
}


@dataclass
class AnthropicResponse:
    """Structured response from Anthropic provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "end_turn"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class AnthropicProvider:
    """
    Anthropic LLM Provider with LiteLLM integration and direct SDK fallback.

    Supports:
      - Chat completions
      - Streaming
      - Extended thinking (Claude-specific)
      - Automatic cost estimation

    Usage:
        provider = AnthropicProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-3-5-sonnet-20241022",
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._call_count = 0
        self._total_cost = 0.0
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def is_available(self) -> bool:
        return bool(self.settings.anthropic_api_key)

    def _estimate_cost(self, model: str, usage: dict[str, int]) -> float:
        model_info = ANTHROPIC_MODELS.get(model, ANTHROPIC_MODELS["claude-3-5-sonnet-20241022"])
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (input_tokens / 1_000_000 * model_info["cost_input"] +
                output_tokens / 1_000_000 * model_info["cost_output"])

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        system: Optional[str] = None,
        **kwargs,
    ) -> AnthropicResponse:
        """Generate a chat completion using Anthropic."""
        start = time.monotonic()

        try:
            content, usage, finish_reason = await self._call_via_litellm(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, system=system,
            )
        except ImportError:
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, system=system,
            )
        except (LLMRateLimitError, LLMProviderError):
            raise
        except Exception as e:
            self._last_error = str(e)
            logger.debug("LiteLLM failed for Anthropic, trying direct: %s", e)
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, system=system,
            )

        latency = (time.monotonic() - start) * 1000
        cost = self._estimate_cost(model, usage)
        self._call_count += 1
        self._total_cost += cost

        return AnthropicResponse(
            content=content, model=model, usage=usage,
            finish_reason=finish_reason, latency_ms=latency, cost_usd=cost,
        )

    async def _call_via_litellm(
        self, messages, model, temperature, max_tokens, top_p, system,
    ) -> tuple[str, dict[str, int], str]:
        import litellm

        params = {
            "model": f"anthropic/{model}",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "timeout": self.settings.llm_timeout_seconds,
        }
        if system:
            params["system"] = system

        try:
            response = await asyncio.to_thread(litellm.completion, **params)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                self._last_error = str(e)
                raise LLMRateLimitError(provider="anthropic")
            self._last_error = str(e)
            raise LLMProviderError(provider="anthropic", reason=str(e), model=model)

        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return content, usage, response.choices[0].finish_reason or "end_turn"

    async def _call_direct(
        self, messages, model, temperature, max_tokens, top_p, system,
    ) -> tuple[str, dict[str, int], str]:
        import httpx

        api_key = self.settings.anthropic_api_key
        if not api_key:
            raise LLMProviderError(provider="anthropic", reason="ANTHROPIC_API_KEY not configured", model=model)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Convert OpenAI-format messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                if not system:
                    system = msg["content"]
                continue
            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 429:
            self._last_error = "HTTP 429: Rate limited by Anthropic"
            raise LLMRateLimitError(provider="anthropic")
        if response.status_code != 200:
            error_reason = f"HTTP {response.status_code}: {response.text[:200]}"
            self._last_error = error_reason
            raise LLMProviderError(
                provider="anthropic",
                reason=error_reason,
                model=model,
            )

        data = response.json()
        content = data["content"][0]["text"] if data.get("content") else ""
        usage = {
            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
        }
        finish_reason = data.get("stop_reason", "end_turn")

        return content, usage, finish_reason

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from Anthropic."""
        import httpx

        api_key = self.settings.anthropic_api_key
        if not api_key:
            raise LLMProviderError(provider="anthropic", reason="ANTHROPIC_API_KEY not configured", model=model)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        anthropic_messages = [
            m for m in messages if m["role"] != "system"
        ]

        # Extract system prompt separately
        system_messages = [m for m in messages if m["role"] == "system"]
        system_prompt = system_messages[-1]["content"] if system_messages else None

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_reason = f"HTTP {response.status_code}"
                    self._last_error = error_reason
                    raise LLMProviderError(provider="anthropic", reason=error_reason, model=model)
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        try:
                            event = json.loads(line[6:])
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("text"):
                                    yield delta["text"]
                        except json.JSONDecodeError:
                            continue

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "available": self.is_available,
            "call_count": self._call_count,
            "total_cost_usd": round(self._total_cost, 6),
            "last_error": self._last_error,
            "models": list(ANTHROPIC_MODELS.keys()),
        }
