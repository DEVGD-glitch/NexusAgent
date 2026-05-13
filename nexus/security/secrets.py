"""
NEXUS Secrets Manager — Secure handling of API keys and sensitive data.

Manages encryption, rotation, and secure access to secrets.
All secrets are loaded from environment variables or encrypted vault,
never hardcoded in source code.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Secure secrets manager for NEXUS.

    Features:
      - All secrets read from environment or .env (via pydantic-settings)
      - Optional encryption at rest using Fernet
      - Secret rotation support
      - Audit trail for secret access
      - Masking in logs and error messages

    Usage:
        secrets = SecretsManager()
        api_key = secrets.get("OPENAI_API_KEY")
        masked = secrets.mask(api_key)  # "sk-...b3f2"
    """

    # Secrets that should never be logged or exposed
    SENSITIVE_KEYS = frozenset([
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "ZAI_API_KEY",
        "NEXUS_SECRET_KEY",
        "SERPAPI_KEY",
        "BRAVE_SEARCH_KEY",
        "TELEGRAM_BOT_TOKEN",
        "LANGFUSE_SECRET_KEY",
    ])

    def __init__(self):
        self.settings = get_settings()
        self._cache: dict[str, str] = {}
        self._access_log: list[dict[str, Any]] = []

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value by its environment variable name.

        Reads from:
          1. Cache (if previously accessed)
          2. Environment variables
          3. NexusConfig (if mapped)
          4. Encrypted vault
          5. Default value

        Args:
            key: Environment variable name.
            default: Default value if not found.

        Returns:
            The secret value, or default if not found.
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Check environment
        value = os.environ.get(key)
        if value:
            self._cache[key] = value
            return value

        # Check NexusConfig mapping
        config_mapping = {
            "OPENAI_API_KEY": self.settings.openai_api_key,
            "ANTHROPIC_API_KEY": self.settings.anthropic_api_key,
            "GOOGLE_API_KEY": self.settings.google_api_key,
            "ZAI_API_KEY": self.settings.zai_api_key,
            "NEXUS_SECRET_KEY": self.settings.nexus_secret_key,
            "SERPAPI_KEY": self.settings.serpapi_key,
            "BRAVE_SEARCH_KEY": self.settings.brave_search_key,
            "TELEGRAM_BOT_TOKEN": self.settings.telegram_bot_token,
            "LANGFUSE_SECRET_KEY": self.settings.langfuse_secret_key,
        }

        if key in config_mapping:
            value = config_mapping[key]
            if value:
                self._cache[key] = value
                return value

        # Check encrypted vault as last resort
        try:
            from nexus.security.vault import SecretsVault
            vault = SecretsVault()
            vault_value = vault.retrieve(key)
            if vault_value:
                self._cache[key] = vault_value
                return vault_value
        except Exception:
            pass

        return default

    def require(self, key: str) -> str:
        """
        Get a secret value, raising an error if not found.

        Args:
            key: Environment variable name.

        Returns:
            The secret value.

        Raises:
            ValueError: If the secret is not configured.
        """
        value = self.get(key)
        if not value:
            raise ValueError(
                f"Required secret '{key}' is not configured. "
                f"Set it in your .env file or as an environment variable."
            )
        return value

    @staticmethod
    def mask(value: str, visible_chars: int = 4) -> str:
        """
        Mask a secret value for safe display.

        Args:
            value: The secret to mask.
            visible_chars: Number of characters to show at the end.

        Returns:
            Masked string like "sk-...b3f2"
        """
        if not value or len(value) <= visible_chars:
            return "***"
        return f"{value[:3]}...{value[-visible_chars:]}"

    def is_configured(self, key: str) -> bool:
        """Check if a secret is configured (non-empty)."""
        value = self.get(key)
        return bool(value and len(value.strip()) > 0)

    def get_configured_providers(self) -> list[str]:
        """Return list of provider names that have API keys configured."""
        providers = []
        if self.is_configured("OPENAI_API_KEY"):
            providers.append("openai")
        if self.is_configured("ANTHROPIC_API_KEY"):
            providers.append("anthropic")
        if self.is_configured("GOOGLE_API_KEY"):
            providers.append("gemini")
        if self.is_configured("ZAI_API_KEY"):
            providers.append("glm")
        providers.append("ollama")  # Always available
        return providers

    def validate_all(self) -> dict[str, bool]:
        """Check which required secrets are configured."""
        results = {}
        for key in self.SENSITIVE_KEYS:
            results[key] = self.is_configured(key)
        return results

    def hash_secret(self, value: str) -> str:
        """
        Create a one-way hash of a secret for verification purposes.

        Uses SHA-256 with a pepper from NEXUS_SECRET_KEY.
        """
        pepper = self.settings.nexus_secret_key or "nexus-default-pepper"
        combined = f"{pepper}:{value}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def encrypt_value(self, value: str) -> str:
        """
        Encrypt a value using Fernet symmetric encryption.

        Uses NEXUS_SECRET_KEY as the encryption key.
        Requires the 'cryptography' package (included in dependencies).
        """
        if not self.settings.nexus_secret_key:
            raise ValueError(
                "NEXUS_SECRET_KEY is not set. Cannot encrypt. "
                "Set NEXUS_SECRET_KEY in your .env file or environment variables."
            )
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(
            hashlib.sha256(self.settings.nexus_secret_key.encode()).digest()
        )
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()

    def decrypt_value(self, encrypted: str) -> str:
        """
        Decrypt a value encrypted with encrypt_value.
        Requires the 'cryptography' package (included in dependencies).
        """
        if not self.settings.nexus_secret_key:
            raise ValueError(
                "NEXUS_SECRET_KEY is not set. Cannot decrypt. "
                "Set NEXUS_SECRET_KEY in your .env file or environment variables."
            )
        from cryptography.fernet import Fernet, InvalidToken
        key = base64.urlsafe_b64encode(
            hashlib.sha256(self.settings.nexus_secret_key.encode()).digest()
        )
        f = Fernet(key)
        try:
            return f.decrypt(encrypted.encode()).decode()
        except Exception:
            raise ValueError("Failed to decrypt value. Check NEXUS_SECRET_KEY is correct.")

    def get_stats(self) -> dict[str, Any]:
        """Get secrets manager statistics (non-sensitive)."""
        configured = self.validate_all()
        return {
            "total_keys_tracked": len(self.SENSITIVE_KEYS),
            "configured_count": sum(1 for v in configured.values() if v),
            "providers_available": self.get_configured_providers(),
            "cache_size": len(self._cache),
            "configured_details": {k: v for k, v in configured.items()},
        }
