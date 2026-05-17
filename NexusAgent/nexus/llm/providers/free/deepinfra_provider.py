"""
NEXUS DeepInfra Provider — Free open-source model inference.

DeepInfra offers free inference for open-source models via
OpenAI-compatible API. No API key required for chat.

Models: Llama 4, Qwen 3, DeepSeek, Mistral, Gemma, Phi, etc.
Docs: https://deepinfra.com
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

DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1"

DEEPINFRA_MODELS = {
    "meta-llama/Llama-4-Maverick-17B": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "meta-llama/Llama-4-Scout-17B": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
    "Qwen/Qwen3-Coder-32B": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "deepseek-ai/DeepSeek-V3-0324": {"context": 65536, "cost_input": 0.0, "cost_output": 0.0},
    "mistralai/Mistral-Small-3.1-24B": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "google/gemma-3-27b-it": {"context": 8192, "cost_input": 0.0, "cost_output": 0.0},
    "microsoft/Phi-4-mini-instruct": {"context": 16384, "cost_input": 0.0, "cost_output": 0.0},
}


@dataclass
class DeepInfraResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class DeepInfraProvider:
    def __init__(self) -> None:
        self.base_url = DEEPINFRA_BASE_URL
        self.http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        return self.http_client

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "meta-llama/Llama-4-Maverick-17B",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> DeepInfraResponse:
        start = time.monotonic()
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {"Content-Type": "application/json"}

        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            elapsed = (time.monotonic() - start) * 1000

            choice = data["choices"][0]
            return DeepInfraResponse(
                content=choice["message"]["content"],
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=elapsed,
                cost_usd=0.0,
            )
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("deepinfra", f"API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise LLMProviderError("deepinfra", f"Request failed: {e}") from e

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
