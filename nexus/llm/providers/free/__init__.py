"""
NEXUS Free Provider Hub — LLM providers at zero cost.
Powered by no-cost-ai ecosystem (github.com/zebbern/no-cost-ai).

Providers:
  - Pollinations: Free, unlimited, OpenAI-compatible (chat + image + video)
  - G4F: 200+ models, OpenAI-compatible, rate-limited
  - DeepInfra: Open-source models, free tier
"""

from nexus.llm.providers.free.pollinations_provider import PollinationsProvider, POLLINATIONS_MODELS
from nexus.llm.providers.free.g4f_provider import G4FProvider, G4F_MODELS
from nexus.llm.providers.free.free_router import FreeProviderRouter

__all__ = [
    "PollinationsProvider",
    "G4FProvider",
    "FreeProviderRouter",
    "POLLINATIONS_MODELS",
    "G4F_MODELS",
]
