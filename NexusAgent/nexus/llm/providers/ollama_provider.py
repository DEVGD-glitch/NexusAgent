"""
NEXUS Ollama Provider — Local LLM via Ollama API.

Runs models locally through Ollama at http://127.0.0.1:11434.
Always available as the ultimate fallback provider since it requires
no API keys. Supports all Ollama models including Llama, Mistral,
Gemma, Phi, CodeLlama, etc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError

logger = logging.getLogger(__name__)

# Popular Ollama models with approximate context sizes
OLLAMA_MODELS = {
    "llama3.1:8b": {"context": 128000, "size": "8b"},
    "llama3.1:70b": {"context": 128000, "size": "70b"},
    "mistral:7b": {"context": 32000, "size": "7b"},
    "mixtral:8x7b": {"context": 32000, "size": "8x7b"},
    "gemma2:9b": {"context": 8192, "size": "9b"},
    "phi3:14b": {"context": 128000, "size": "14b"},
    "codellama:13b": {"context": 16384, "size": "13b"},
    "qwen2.5:7b": {"context": 131072, "size": "7b"},
    "deepseek-coder:6.7b": {"context": 16384, "size": "6.7b"},
}


@dataclass
class OllamaResponse:
    """Structured response from Ollama provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0


class OllamaProvider:
    """
    Ollama LLM Provider — local model inference via Ollama API.

    Ollama is the ultimate fallback provider since it requires no API
    keys and runs entirely locally. It supports all models available
    through the Ollama registry.

    Supports:
      - Chat completions via /api/chat
      - Text generation via /api/generate
      - Streaming via SSE
      - Model listing and management
      - Embeddings via /api/embeddings
      - Model pull/delete operations

    Usage:
        provider = OllamaProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="llama3.1:8b",
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._call_count = 0
        self._last_error: Optional[str] = None
        self._available_models: list[str] = []

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def is_available(self) -> bool:
        """Ollama is always potentially available (local)."""
        return True

    @property
    def base_url(self) -> str:
        return self.settings.ollama_base_url

    async def check_connection(self) -> bool:
        """Check if Ollama server is actually running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models on the Ollama server."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    self._available_models = [m["name"] for m in models]
                    return models
                return []
        except (httpx.ConnectError, httpx.TimeoutException):
            return []

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
        **kwargs,
    ) -> OllamaResponse:
        """
        Generate a chat completion using Ollama.

        Args:
            messages: List of message dicts.
            model: Model name (default from config: ollama_default_model).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate (num_predict).
            top_p: Top-p sampling.
            repeat_penalty: Repetition penalty.

        Returns:
            OllamaResponse with content and metadata.
        """
        start = time.monotonic()
        model = model or self.settings.ollama_default_model

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": top_p,
                "repeat_penalty": repeat_penalty,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            self._last_error = f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            raise LLMProviderError(
                provider="ollama",
                reason=f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?",
                model=model,
            ) from e
        except httpx.TimeoutException as e:
            self._last_error = f"Request timed out after {self.settings.llm_timeout_seconds}s"
            raise LLMProviderError(
                provider="ollama",
                reason=f"Request timed out after {self.settings.llm_timeout_seconds}s",
                model=model,
            ) from e

        if response.status_code != 200:
            error_reason = f"HTTP {response.status_code}: {response.text[:200]}"
            self._last_error = error_reason
            raise LLMProviderError(
                provider="ollama",
                reason=error_reason,
                model=model,
            )

        data = response.json()
        content = data.get("message", {}).get("content", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        latency = (time.monotonic() - start) * 1000
        self._call_count += 1

        return OllamaResponse(
            content=content, model=model, usage=usage,
            finish_reason="stop", latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from Ollama."""
        model = model or self.settings.ollama_default_model
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_reason = f"HTTP {response.status_code}"
                    self._last_error = error_reason
                    raise LLMProviderError(
                        provider="ollama",
                        reason=error_reason,
                        model=model,
                    )
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        content = event.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if event.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> OllamaResponse:
        """
        Generate text from a single prompt (non-chat interface).

        Uses Ollama's /api/generate endpoint.
        """
        model = model or self.settings.ollama_default_model
        start = time.monotonic()

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            self._last_error = str(e)
            raise LLMProviderError(provider="ollama", reason=str(e), model=model)

        if response.status_code != 200:
            error_reason = f"HTTP {response.status_code}: {response.text[:200]}"
            self._last_error = error_reason
            raise LLMProviderError(
                provider="ollama",
                reason=error_reason,
                model=model,
            )

        data = response.json()
        content = data.get("response", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        latency = (time.monotonic() - start) * 1000
        self._call_count += 1

        return OllamaResponse(
            content=content, model=model, usage=usage,
            finish_reason="stop", latency_ms=latency,
        )

    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from the Ollama registry."""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False},
                )
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def get_embeddings(self, prompt: str, model: str = "nomic-embed-text") -> list[float]:
        """Get embeddings for a text using Ollama's embedding endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": model, "prompt": prompt},
                )
                if response.status_code == 200:
                    return response.json().get("embedding", [])
                raise LLMProviderError(provider="ollama", reason=f"Embedding failed: HTTP {response.status_code}", model=model)
        except httpx.ConnectError:
            self._last_error = "Cannot connect to Ollama"
            raise LLMProviderError(provider="ollama", reason="Cannot connect to Ollama", model=model)

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "available": self.is_available,
            "base_url": self.base_url,
            "default_model": self.settings.ollama_default_model,
            "call_count": self._call_count,
            "last_error": self._last_error,
            "known_models": list(OLLAMA_MODELS.keys()),
            "available_models": self._available_models,
        }
