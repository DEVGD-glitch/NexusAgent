"""NEXUS LLM — Multi-LLM routing with fallback chains."""

from nexus.llm.router import LLMRouter, Provider, TaskComplexity, LLMResponse

__all__ = [
    "LLMRouter",
    "Provider",
    "TaskComplexity",
    "LLMResponse",
    "FallbackChain",
]


def __getattr__(name):
    """Lazy import for optional modules."""
    if name == "FallbackChain":
        from nexus.llm.fallback import FallbackChain
        return FallbackChain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
