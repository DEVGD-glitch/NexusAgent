"""
NEXUS Free Provider Router — Routes requests to the best available free provider.

Strategy:
  1. Try Pollinations.ai first (unlimited, no key needed, fastest)
  2. Fallback to G4F.dev (200+ models, rate-limited per IP)
  3. Log all costs (always $0.00 but tracks usage for transparency)
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional

from nexus.core.exceptions import LLMAllProvidersFailedError
from nexus.llm.providers.free.pollinations_provider import PollinationsProvider, PollinationsResponse
from nexus.llm.providers.free.g4f_provider import G4FProvider, G4FResponse

logger = logging.getLogger(__name__)


class FreeProviderRouter:
    """
    Routes LLM requests across free providers with automatic fallback.

    Tries providers in order: Pollinations → G4F → error
    """

    def __init__(self) -> None:
        self.pollinations = PollinationsProvider()
        self.g4f = G4FProvider()

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> PollinationsResponse | G4FResponse:
        errors: list[str] = []

        if model and model in G4F_MODELS:
            return await self.g4f.complete(messages, model=model, temperature=temperature, max_tokens=max_tokens)

        try:
            result = await self.pollinations.complete(
                messages, model=model or "openai", temperature=temperature, max_tokens=max_tokens
            )
            logger.info(f"[FreeRouter] Pollinations success: {len(result.content)} chars")
            return result
        except Exception as e:
            errors.append(f"Pollinations: {e}")
            logger.warning(f"[FreeRouter] Pollinations failed, trying G4F: {e}")

        try:
            result = await self.g4f.complete(
                messages, model=model or "gpt-4o-mini", temperature=temperature, max_tokens=max_tokens
            )
            logger.info(f"[FreeRouter] G4F success: {len(result.content)} chars")
            return result
        except Exception as e:
            errors.append(f"G4F: {e}")

        raise LLMAllProvidersFailedError(
            f"All free providers failed: {'; '.join(errors)}",
            provider_errors={},
        )

    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        if model and model in G4F_MODELS:
            async for chunk in await self.g4f.complete_stream(messages, model=model, temperature=temperature, max_tokens=max_tokens):
                yield chunk
            return

        try:
            async for chunk in self.pollinations.complete_stream(
                messages, model=model or "openai", temperature=temperature, max_tokens=max_tokens
            ):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[FreeRouter] Pollinations stream failed, trying G4F: {e}")

        async for chunk in self.g4f.complete_stream(
            messages, model=model or "gpt-4o-mini", temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk

    async def close(self) -> None:
        await self.pollinations.close()
        await self.g4f.close()
