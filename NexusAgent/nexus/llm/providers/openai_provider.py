"""
NEXUS OpenAI Provider — GPT-4o, GPT-4o-mini via OpenAI API.

First-class provider implementation using both LiteLLM and direct
OpenAI SDK calls with automatic fallback between them.
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

# OpenAI model catalog with pricing and context info
OPENAI_MODELS = {
    "gpt-4o": {"context": 128000, "cost_input": 2.50, "cost_output": 10.00},
    "gpt-4o-mini": {"context": 128000, "cost_input": 0.15, "cost_output": 0.60},
    "gpt-4-turbo": {"context": 128000, "cost_input": 10.00, "cost_output": 30.00},
    "o1": {"context": 200000, "cost_input": 15.00, "cost_output": 60.00},
    "o1-mini": {"context": 128000, "cost_input": 3.00, "cost_output": 12.00},
    "o3-mini": {"context": 200000, "cost_input": 1.10, "cost_output": 4.40},
}


@dataclass
class OpenAIResponse:
    """Structured response from OpenAI provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class OpenAIProvider:
    """
    OpenAI LLM Provider with LiteLLM integration and direct SDK fallback.

    Supports:
      - Chat completions (sync and async)
      - Streaming responses
      - Automatic cost estimation
      - Rate limit handling
      - Model-specific parameter tuning

    Usage:
        provider = OpenAIProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
        )
        print(response.content)
    """

    def __init__(self):
        self.settings = get_settings()
        self._call_count = 0
        self._total_cost = 0.0
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.settings.openai_api_key)

    def _estimate_cost(self, model: str, usage: dict[str, int]) -> float:
        """Estimate the cost of an API call based on token usage."""
        model_info = OPENAI_MODELS.get(model, OPENAI_MODELS["gpt-4o"])
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1_000_000 * model_info["cost_input"] +
                output_tokens / 1_000_000 * model_info["cost_output"])
        return cost

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        json_mode: bool = False,
        **kwargs,
    ) -> OpenAIResponse:
        """
        Generate a chat completion using OpenAI.

        Tries LiteLLM first, then falls back to direct OpenAI SDK.

        Args:
            messages: List of message dicts.
            model: Model name (gpt-4o, gpt-4o-mini, etc.).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            top_p: Top-p sampling parameter.
            frequency_penalty: Frequency penalty.
            presence_penalty: Presence penalty.
            json_mode: Force JSON output.

        Returns:
            OpenAIResponse with content and metadata.

        Raises:
            LLMProviderError: If the API call fails.
            LLMRateLimitError: If rate limited.
        """
        start = time.monotonic()

        try:
            content, usage, finish_reason = await self._call_via_litellm(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p,
                frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                json_mode=json_mode,
            )
        except ImportError:
            logger.debug("LiteLLM not available, using direct OpenAI SDK")
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p,
                frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                json_mode=json_mode,
            )
        except LLMRateLimitError:
            raise
        except LLMProviderError:
            # Try direct SDK as fallback
            logger.debug("LiteLLM failed, trying direct OpenAI SDK")
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p,
                frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                json_mode=json_mode,
            )

        latency = (time.monotonic() - start) * 1000
        cost = self._estimate_cost(model, usage)

        self._call_count += 1
        self._total_cost += cost

        return OpenAIResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency,
            cost_usd=cost,
        )

    async def _call_via_litellm(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        json_mode: bool,
    ) -> tuple[str, dict[str, int], str]:
        """Call OpenAI via LiteLLM unified interface."""
        import litellm

        params = {
            "model": f"openai/{model}",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "timeout": self.settings.llm_timeout_seconds,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        try:
            response = await asyncio.to_thread(litellm.completion, **params)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                self._last_error = str(e)
                raise LLMRateLimitError(provider="openai")
            self._last_error = str(e)
            raise LLMProviderError(provider="openai", reason=str(e), model=model)

        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        finish_reason = response.choices[0].finish_reason or "stop"

        return content, usage, finish_reason

    async def _call_direct(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        json_mode: bool,
    ) -> tuple[str, dict[str, int], str]:
        """Call OpenAI directly via the openai Python SDK."""
        from openai import AsyncOpenAI

        api_key = self.settings.openai_api_key
        if not api_key:
            raise LLMProviderError(provider="openai", reason="OPENAI_API_KEY not configured", model=model)

        client = AsyncOpenAI(api_key=api_key, timeout=self.settings.llm_timeout_seconds)

        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**params)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                self._last_error = str(e)
                raise LLMRateLimitError(provider="openai")
            self._last_error = str(e)
            raise LLMProviderError(provider="openai", reason=str(e), model=model)

        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        finish_reason = response.choices[0].finish_reason or "stop"

        return content, usage, finish_reason

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from OpenAI."""
        from openai import AsyncOpenAI

        api_key = self.settings.openai_api_key
        if not api_key:
            raise LLMProviderError(provider="openai", reason="OPENAI_API_KEY not configured", model=model)

        client = AsyncOpenAI(api_key=api_key, timeout=self.settings.llm_timeout_seconds)

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                self._last_error = str(e)
                raise LLMRateLimitError(provider="openai")
            self._last_error = str(e)
            raise LLMProviderError(provider="openai", reason=str(e), model=model)

    def get_stats(self) -> dict[str, Any]:
        """Return provider usage statistics."""
        return {
            "provider": "openai",
            "available": self.is_available,
            "call_count": self._call_count,
            "total_cost_usd": round(self._total_cost, 6),
            "last_error": self._last_error,
            "models": list(OPENAI_MODELS.keys()),
        }
