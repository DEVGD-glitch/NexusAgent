"""
NEXUS Secrets Vault — Encrypted local storage for API keys.

API keys are never stored in plaintext in .env files.
Instead, they are encrypted with a key derived from a
machine-specific identifier or user password.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SecretsVault:
    """
    Encrypted local storage for API keys and secrets.

    Uses Fernet symmetric encryption (from cryptography package).
    The encryption key is derived from:
      1. A machine-specific random pepper (stored in ~/.nexus/.pepper)
      2. Platform identifiers (node, machine, system)
      3. User-controlled derivation via password env var (optional)

    This ensures secrets are tied to this machine AND require access
    to the pepper file. Even if platform identifiers are known,
    the pepper cannot be guessed.

    Usage:
        vault = SecretsVault()
        vault.store("OPENAI_API_KEY", "sk-...")
        key = vault.retrieve("OPENAI_API_KEY")
    """

    def __init__(self, vault_dir: Optional[str] = None):
        self.vault_dir = Path(vault_dir or os.path.join(
            os.path.expanduser("~"), ".nexus", "vault"
        ))
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self._pepper_file = Path(os.path.expanduser("~")) / ".nexus" / ".pepper"
        self._key = self._derive_key()
        self._fernet = None

    def _get_pepper(self) -> bytes:
        """Get or create the machine-specific pepper."""
        if self._pepper_file.exists():
            try:
                return self._pepper_file.read_bytes()
            except Exception:
                pass
        # Generate new pepper atomically using temp file + rename
        import secrets
        pepper = secrets.token_bytes(32)
        self._pepper_file.parent.mkdir(parents=True, exist_ok=True)
        # Write to temp file first, then rename to prevent TOCTOU races
        tmp_path = self._pepper_file.parent / f".pepper.tmp.{os.urandom(4).hex()}"
        try:
            tmp_path.write_bytes(pepper)
            tmp_path.rename(self._pepper_file)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        logger.warning(
            "Cannot set restricted permissions on pepper file on this platform; "
            "pepper file at %s relies on file system access controls",
            self._pepper_file,
        )
        logger.info("Created new machine pepper at %s", self._pepper_file)
        return pepper

    def _derive_key(self) -> bytes:
        """Derive an encryption key from pepper + platform identifiers."""
        # Pepper is the primary secret (random, stored in file)
        pepper = self._get_pepper()
        # Platform identifiers add machine-binding
        identifiers = [
            platform.node(),
            platform.machine(),
            platform.system(),
            os.getenv("USERNAME", os.getenv("USER", "nexus")),
        ]
        combined = pepper + "|".join(identifiers).encode()
        key = hashlib.sha256(combined).digest()
        # Key stretching to slow down brute force attacks
        key = hashlib.pbkdf2_hmac("sha256", key, salt=b"nexus-vault", iterations=600000)
        return key

    def _get_fernet(self):
        """Get or create Fernet cipher."""
        if self._fernet is None:
            try:
                from cryptography.fernet import Fernet
                import base64
                key = base64.urlsafe_b64encode(self._key)
                self._fernet = Fernet(key)
            except ImportError:
                logger.warning("cryptography package not available. Vault encryption disabled.")
                self._fernet = None
        return self._fernet

    def store(self, key: str, value: str) -> bool:
        """
        Store a secret in the vault.

        Args:
            key: Secret identifier (e.g., 'OPENAI_API_KEY')
            value: The secret value to encrypt and store

        Returns:
            True if stored successfully.
        """
        try:
            fernet = self._get_fernet()
            if fernet is None:
                raise RuntimeError(
                    "cryptography package required but not available. "
                    "Install with: pip install cryptography"
                )
            encrypted = fernet.encrypt(value.encode())
            data = base64.b64encode(encrypted).decode()

            vault_file = self.vault_dir / f"{key}.vault"
            vault_file.write_text(data, encoding="utf-8")
            logger.info("Stored secret: %s", key)
            return True
        except Exception as exc:
            logger.error("Failed to store secret %s: %s", key, exc)
            return False

    def retrieve(self, key: str) -> Optional[str]:
        """
        Retrieve a secret from the vault.

        Args:
            key: Secret identifier

        Returns:
            The decrypted secret value, or None if not found.
        """
        try:
            vault_file = self.vault_dir / f"{key}.vault"
            if not vault_file.exists():
                return None

            data = vault_file.read_text(encoding="utf-8")
            encrypted = base64.b64decode(data.encode())

            fernet = self._get_fernet()
            if fernet is None:
                raise RuntimeError(
                    "cryptography package required but not available. "
                    "Install with: pip install cryptography"
                )
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as exc:
            logger.error("Failed to retrieve secret %s: %s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """Delete a secret from the vault."""
        try:
            vault_file = self.vault_dir / f"{key}.vault"
            if vault_file.exists():
                vault_file.unlink()
                logger.info("Deleted secret: %s", key)
            return True
        except Exception as exc:
            logger.error("Failed to delete secret %s: %s", key, exc)
            return False

    def list_keys(self) -> list[str]:
        """List all stored secret identifiers."""
        return [
            f.stem for f in self.vault_dir.glob("*.vault")
        ]

    def check_all(self) -> dict[str, bool]:
        """Check which secrets are configured."""
        keys = self.list_keys()
        return {key: True for key in keys}

    def migrate_from_env(self, env_file: str = ".env") -> int:
        """
        Migrate API keys from .env file to the encrypted vault.
        Removes the keys from .env after migration.

        Returns:
            Number of keys migrated.
        """
        env_path = Path(env_file)
        if not env_path.exists():
            return 0

        api_key_prefixes = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
            "ZAI_API_KEY", "SERPAPI_KEY", "BRAVE_SEARCH_KEY",
            "TELEGRAM_BOT_TOKEN",
        ]

        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        migrated = 0

        for line in lines:
            stripped = line.strip()
            for key_prefix in api_key_prefixes:
                if stripped.startswith(f"{key_prefix}="):
                    value = stripped[len(key_prefix) + 1:].strip()
                    if value and value != '""' and value != "''":
                        self.store(key_prefix, value)
                        new_lines.append(f"# {key_prefix} (migrated to vault)")
                        migrated += 1
                        break
            else:
                new_lines.append(line)

        if migrated > 0:
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.info("Migrated %d API keys to vault", migrated)

        return migrated
