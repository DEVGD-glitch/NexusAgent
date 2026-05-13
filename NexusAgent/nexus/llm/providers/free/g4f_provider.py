"""
NEXUS G4F Provider — 200+ free models via g4f.dev.

G4F (Free AI API) provides access to 200+ LLMs through an
OpenAI-compatible API. Models include GPT-4o, Claude, Gemini,
DeepSeek, Grok, Llama, and many more.

Docs: https://g4f.dev
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError

logger = logging.getLogger(__name__)

G4F_BASE_URL = "https://api.g4f.dev/v1"

G4F_MODELS = {
    "gpt-4o": {"context": 128000, "cost_input": 0.0, "cost_output": 0.0},
    "gpt-4o-mini": {"context": 128000, "cost_input": 0.0, "cost_output": 0.0},
    "claude-sonnet-4": {"context": 128000, "cost_input": 0.0, "cost_output": 0.0},
    "claude-haiku-3.5": {"context": 128000, "cost_input": 0.0, "cost_output": 0.0},
    "gemini-2.0-flash": {"context": 1048576, "cost_input": 0.0, "cost_output": 0.0},
    "deepseek-v3": {"context": 65536, "cost_input": 0.0, "cost_output": 0.0},
    "deepseek-r1": {"context": 65536, "cost_input": 0.0, "cost_output": 0.0},
    "grok-3-mini": {"context": 131072, "cost_input": 0.0, "cost_output": 0.0},
    "llama-4-maverick": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "llama-4-scout": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "qwen-3-coder": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "mistral-small-3.1": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "phi-4": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
}


@dataclass
class G4FResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class G4FProvider:
    """
    G4F.dev free LLM provider. OpenAI-compatible, requires random user ID as API key.

    Usage:
        provider = G4FProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
        )
    """

    def __init__(self) -> None:
        self.base_url = G4F_BASE_URL
        self.http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self.http_client

    async def _get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer free",  # G4F accepts any non-empty key
        }

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> G4FResponse:
        start = time.monotonic()
        client = await self._get_client()

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
                headers=await self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            elapsed = (time.monotonic() - start) * 1000

            choice = data["choices"][0]
            return G4FResponse(
                content=choice["message"]["content"],
                model=data.get("model", model),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=elapsed,
                cost_usd=0.0,
            )
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(f"G4F API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise LLMProviderError(f"G4F request failed: {e}") from e

    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o-mini",
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
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions",
                headers=await self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            if content := data.get("choices", [{}])[0].get("delta", {}).get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(f"G4F stream error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise LLMProviderError(f"G4F stream failed: {e}") from e

    async def list_models(self) -> list[str]:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/models", headers=await self._get_headers())
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"G4F list_models failed: {e}")
            return list(G4F_MODELS.keys())

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
