"""
NEXUS Core Configuration — pydantic-settings based configuration.

Loads all settings from environment variables and .env files.
Every API key, URL, and tunable parameter is defined here.
No secrets are ever hardcoded.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NexusConfig(BaseSettings):
    """
    Central configuration for NEXUS agent platform.

    All values are read from environment variables or .env file.
    Use NexusConfig() to get a cached singleton, or get_settings() for
    the LRU-cached version.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────
    nexus_env: Environment = Environment.DEVELOPMENT
    nexus_log_level: LogLevel = LogLevel.INFO
    nexus_secret_key: str = "change-me-to-a-secure-random-string"
    nexus_host: str = "0.0.0.0"
    nexus_port: int = 8081
    nexus_working_dir: str = "./nexus_data"

    # ── LLM Provider Keys ──────────────────────────────────────
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    zai_api_key: Optional[str] = None
    zai_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    openbig_model_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    cerebras_api_key: Optional[str] = None
    together_api_key: Optional[str] = None

    # ── Ollama (local LLM) ─────────────────────────────────────
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "llama3.1:8b"

    # ── ChromaDB ────────────────────────────────────────────────
    chroma_persist_dir: str = "./nexus_data/chroma"
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # ── Browser Service ────────────────────────────────────────
    browser_service_url: str = "http://localhost:8001"
    browser_service_enabled: bool = True

    # ── Security ───────────────────────────────────────────────
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10
    sandbox_enabled: bool = True
    sandbox_docker_image: str = "nexus-sandbox:latest"
    audit_log_dir: str = "./nexus_data/audit"

    # ── Telegram Bot ───────────────────────────────────────────
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # ── Web Search ─────────────────────────────────────────────
    serpapi_key: Optional[str] = None
    brave_search_key: Optional[str] = None

    # ── Observability ──────────────────────────────────────────
    otel_exporter_otlp_endpoint: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None

    # ── Context7 ────────────────────────────────────────────────
    context7_api_key: Optional[str] = None

    # ── Puter.js ───────────────────────────────────────────────
    puter_api_url: str = "https://api.puter.com"

    # ── Memory Settings ────────────────────────────────────────
    memory_max_working_tokens: int = 30000
    memory_compression_threshold: float = 0.8
    memory_default_top_k: int = 5

    # ── LLM Router Settings ────────────────────────────────────
    llm_default_provider: str = "gemini"
    llm_default_model: str = "gemini-2.5-flash"
    llm_fallback_chain: str = "gemini,groq,openrouter,nvidia,cerebras,openai,anthropic,glm,ollama,pollinations"
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3

    # ── Orchestrator Settings ──────────────────────────────────
    orchestrator_max_iterations: int = 25
    orchestrator_checkpointer: str = "memory"
    orchestrator_interrupt_before_executor: bool = True

    @field_validator("nexus_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("nexus_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        is_default = v == "change-me-to-a-secure-random-string"
        if not is_default:
            return v
        env = info.data.get("nexus_env", os.getenv("NEXUS_ENV", "development"))
        if env == "production":
            raise ValueError(
                "NEXUS_SECRET_KEY must be changed from default in production. "
                "Set the NEXUS_SECRET_KEY environment variable to a secure random string."
            )
        import logging
        logging.warning(
            "NEXUS_SECRET_KEY is still set to the default value. "
            "This is INSECURE. Generate a strong key with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
        return v

    @property
    def is_production(self) -> bool:
        return self.nexus_env == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.nexus_env == Environment.DEVELOPMENT

    @property
    def available_providers(self) -> list[str]:
        """Return list of LLM providers that have API keys configured.
        Free/no-key providers are always available."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("gemini")
        if self.zai_api_key or self.openbig_model_api_key:
            providers.append("glm")
        if self.groq_api_key:
            providers.append("groq")
        if self.openrouter_api_key:
            providers.append("openrouter")
        if self.nvidia_api_key:
            providers.append("nvidia")
        if self.cerebras_api_key:
            providers.append("cerebras")
        if self.together_api_key:
            providers.append("together")
        providers.append("ollama")
        providers.append("pollinations")
        providers.append("g4f")
        providers.append("deepinfra")
        return providers

    @property
    def fallback_providers(self) -> list[str]:
        """Return the fallback chain as an ordered list of provider names."""
        chain = self.llm_fallback_chain.split(",")
        available = self.available_providers
        return [p.strip() for p in chain if p.strip() in available]


@lru_cache()
def get_settings() -> NexusConfig:
    """Return a cached NexusConfig singleton. Use this everywhere."""
    return NexusConfig()


def reload_settings() -> NexusConfig:
    """Force-reload settings (useful for tests)."""
    get_settings.cache_clear()
    return get_settings()
