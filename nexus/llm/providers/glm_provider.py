"""
NEXUS GLM Provider — GLM-4-Plus, GLM-5 via ZAI API (BigModel).

First-class provider — this is NOT an afterthought. The ZAI API is a
primary provider in the NEXUS architecture, on par with OpenAI.
Supports direct HTTP API calls with full feature parity.
"""

from __future__ import annotations

import asyncio
import email.utils
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError, LLMRateLimitError

logger = logging.getLogger(__name__)

GLM_MODELS = {
    "glm-4-plus": {"context": 128000, "cost_input": 0.50, "cost_output": 0.50},
    "glm-4-flash": {"context": 128000, "cost_input": 0.10, "cost_output": 0.10},
    "glm-4-long": {"context": 1048576, "cost_input": 0.10, "cost_output": 0.10},
    "glm-4-air": {"context": 128000, "cost_input": 0.01, "cost_output": 0.01},
    "glm-4-airx": {"context": 8192, "cost_input": 0.01, "cost_output": 0.01},
    "glm-4v": {"context": 8192, "cost_input": 0.10, "cost_output": 0.10, "vision": True},
    "cogview-3-flash": {"context": 4096, "cost_input": 0.00, "cost_output": 0.00, "image_gen": True},
}


@dataclass
class GLMResponse:
    """Structured response from GLM/ZAI provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class GLMProvider:
    """
    GLM/ZAI LLM Provider — first-class provider via BigModel API.

    The ZAI API provides access to the GLM family of models including
    GLM-4-Plus and GLM-4V (vision). This provider is treated as a
    first-class citizen in the NEXUS architecture, equal to OpenAI.

    Supports:
      - Chat completions with full OpenAI-compatible API
      - Streaming via SSE
      - Vision (GLM-4V)
      - Image generation (CogView)
      - Function calling / tool use
      - Long context (GLM-4-Long: 1M tokens)

    Usage:
        provider = GLMProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="glm-4-plus",
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._call_count = 0
        self._total_cost = 0.0
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "glm"

    @property
    def is_available(self) -> bool:
        return bool(self.settings.zai_api_key)

    @property
    def base_url(self) -> str:
        return self.settings.zai_base_url

    def _estimate_cost(self, model: str, usage: dict[str, int]) -> float:
        model_info = GLM_MODELS.get(model, GLM_MODELS["glm-4-plus"])
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (input_tokens / 1_000_000 * model_info["cost_input"] +
                output_tokens / 1_000_000 * model_info["cost_output"])

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "glm-4-plus",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> GLMResponse:
        """
        Generate a chat completion using GLM via ZAI API.

        The ZAI API is OpenAI-compatible, so we use the same /chat/completions
        endpoint format with ZAI-specific headers.

        Args:
            messages: List of message dicts.
            model: GLM model name.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            top_p: Top-p sampling.
            tools: Optional function/tool definitions for tool calling.
            tool_choice: Tool choice strategy.
            json_mode: Force JSON output.

        Returns:
            GLMResponse with content and metadata.
        """
        start = time.monotonic()

        api_key = self.settings.zai_api_key
        if not api_key:
            raise LLMProviderError(provider="glm", reason="ZAI_API_KEY not configured", model=model)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            self._last_error = f"Request timed out after {self.settings.llm_timeout_seconds}s"
            raise LLMProviderError(provider="glm", reason=f"Request timed out after {self.settings.llm_timeout_seconds}s", model=model) from e
        except httpx.ConnectError as e:
            self._last_error = f"Cannot connect to ZAI API at {self.base_url}"
            raise LLMProviderError(provider="glm", reason=f"Cannot connect to ZAI API at {self.base_url}", model=model) from e

        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            if retry_after is not None:
                try:
                    retry_after = int(retry_after)
                except ValueError:
                    # Retry-After may be an HTTP-date (RFC 7231)
                    try:
                        retry_date = email.utils.parsedate_to_datetime(retry_after)
                        retry_after = int((retry_date - datetime.now(timezone.utc)).total_seconds())
                        if retry_after < 0:
                            retry_after = 0
                    except Exception:
                        retry_after = None
            self._last_error = "HTTP 429: Rate limited by ZAI API"
            raise LLMRateLimitError(provider="glm", retry_after=retry_after)
        if response.status_code == 401:
            self._last_error = "Invalid ZAI_API_KEY"
            raise LLMProviderError(provider="glm", reason="Invalid ZAI_API_KEY", model=model)
        if response.status_code != 200:
            error_reason = f"HTTP {response.status_code}: {response.text[:300]}"
            self._last_error = error_reason
            raise LLMProviderError(
                provider="glm",
                reason=error_reason,
                model=model,
            )

        data = response.json()

        # Parse response — OpenAI-compatible format
        choices = data.get("choices", [])
        if not choices:
            raise LLMProviderError(provider="glm", reason="No choices in response", model=model)

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # Handle tool calls in response
        tool_calls = message.get("tool_calls")
        if tool_calls:
            content = json.dumps({"content": content, "tool_calls": tool_calls})

        finish_reason = choice.get("finish_reason", "stop")

        usage_data = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }

        latency = (time.monotonic() - start) * 1000
        cost = self._estimate_cost(model, usage)
        self._call_count += 1
        self._total_cost += cost

        return GLMResponse(
            content=content, model=model, usage=usage,
            finish_reason=finish_reason, latency_ms=latency, cost_usd=cost,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str = "glm-4-plus",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from GLM via SSE."""
        api_key = self.settings.zai_api_key
        if not api_key:
            raise LLMProviderError(provider="glm", reason="ZAI_API_KEY not configured", model=model)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_reason = f"HTTP {response.status_code}"
                    self._last_error = error_reason
                    raise LLMProviderError(
                        provider="glm",
                        reason=error_reason,
                        model=model,
                    )
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                            delta = event.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, IndexError):
                            continue

    async def vision(
        self,
        prompt: str,
        image_url: str,
        model: str = "glm-4v",
    ) -> GLMResponse:
        """
        Analyze an image using GLM-4V vision model.

        Args:
            prompt: Text prompt about the image.
            image_url: URL of the image to analyze.
            model: Vision model (default: glm-4v).

        Returns:
            GLMResponse with the analysis.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]
        return await self.complete(messages=messages, model=model)

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": "glm",
            "available": self.is_available,
            "call_count": self._call_count,
            "total_cost_usd": round(self._total_cost, 6),
            "last_error": self._last_error,
            "base_url": self.base_url,
            "models": list(GLM_MODELS.keys()),
        }
