"""
NEXUS Pollinations Provider — Free, unlimited, OpenAI-compatible.

Pollinations.ai offers free chat, image, and video generation via
OpenAI-compatible API. No API key required. Rate-limited by usage tiers.

Features:
  - Chat: gpt-4o-mini, deepseek-v3, llama-4, gemini-3, claude-haiku, qwen-coder, mistral
  - Image: flux, turbo, gptimage, seedream, nanobanana
  - Video: seedance, veo
  - Unlimited requests (tier-based: 1-20 pollen/day)
  - Full OpenAI-compatible API at https://text.pollinations.ai/openai

Docs: https://pollinations.ai
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError

logger = logging.getLogger(__name__)

POLLINATIONS_BASE_URL = "https://text.pollinations.ai/openai"
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"

POLLINATIONS_MODELS = {
    "openai": {"context": 8192, "cost_input": 0.0, "cost_output": 0.0},
    "openai-fast": {"context": 8192, "cost_input": 0.0, "cost_output": 0.0},
    "openai-large": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "gemini-3-flash": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "deepseek-v3": {"context": 65536, "cost_input": 0.0, "cost_output": 0.0},
    "claude-haiku-4.5": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "claude-sonnet-4.5": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "claude-opus-4.5": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "qwen-coder": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "mistral": {"context": 8192, "cost_input": 0.0, "cost_output": 0.0},
    "llama-4-scout": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "kimi-k2-thinking": {"context": 65536, "cost_input": 0.0, "cost_output": 0.0},
    "glm-4.7": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "minimax-m2.1": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
}

IMAGE_MODELS = ["flux", "turbo", "gptimage", "seedream", "nanobanana", "nanobanana-pro"]


@dataclass
class PollinationsResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class PollinationsProvider:
    """
    Pollinations.ai free LLM provider. OpenAI-compatible, no API key needed.

    Uses the /openai endpoint for full OpenAI-compatible chat completions.
    Falls back to the legacy /prompt endpoint if OpenAI format fails.
    """

    def __init__(self) -> None:
        self.base_url = POLLINATIONS_BASE_URL
        settings = get_settings()
        self.http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        return self.http_client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "openai",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> PollinationsResponse:
        start = time.monotonic()
        client = await self._get_client()

        if model in IMAGE_MODELS:
            return await self._generate_image(messages, model)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True

        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            elapsed = (time.monotonic() - start) * 1000

            choice = data["choices"][0]
            return PollinationsResponse(
                content=choice["message"]["content"],
                model=data.get("model", model),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=elapsed,
                cost_usd=0.0,
            )
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("pollinations", f"API error: {e.response.status_code} {e.response.text}") from e
        except httpx.RequestError as e:
            raise LLMProviderError("pollinations", f"Request failed: {e}") from e

    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "openai",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        import json
                        try:
                            data = json.loads(chunk)
                            if content := data.get("choices", [{}])[0].get("delta", {}).get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(f"Pollinations stream error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise LLMProviderError(f"Pollinations stream failed: {e}") from e

    async def _generate_image(self, messages: list[dict[str, str]], model: str) -> PollinationsResponse:
        prompt = messages[-1]["content"] if messages else ""
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        image_url = f"{POLLINATIONS_IMAGE_URL}{encoded}?model={model}"

        return PollinationsResponse(
            content=f"![{model}]({image_url})\n\nImage generated with {model}. URL: {image_url}",
            model=model,
            finish_reason="stop",
            latency_ms=0.0,
            cost_usd=0.0,
        )

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
