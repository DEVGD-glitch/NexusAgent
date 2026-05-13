"""
NEXUS Puter.js Proxy — Proxy for Puter.js cloud API.

Provides a bridge to Puter.js cloud services for:
  - Cloud storage operations
  - Key-value store
  - Website hosting
  - Email sending
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class PuterProxy:
    """
    Puter.js cloud API proxy.

    Usage:
        proxy = PuterProxy()
        result = await proxy.kv_set("my_key", "my_value")
        value = await proxy.kv_get("my_key")
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.puter_api_url

    async def kv_set(self, key: str, value: str) -> bool:
        """Set a key-value pair in Puter KV store."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/drivers/kv",
                    json={"operation": "set", "key": key, "value": value},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Puter KV set failed: %s", e)
            return False

    async def kv_get(self, key: str) -> Optional[str]:
        """Get a value from Puter KV store."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/drivers/kv",
                    json={"operation": "get", "key": key},
                )
                if response.status_code == 200:
                    return response.json().get("value")
        except Exception as e:
            logger.error("Puter KV get failed: %s", e)
        return None

    async def write_file(self, path: str, content: str) -> bool:
        """Write a file to Puter cloud storage."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/drivers/fs/write",
                    json={"path": path, "content": content},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Puter write failed: %s", e)
            return False

    async def read_file(self, path: str) -> Optional[str]:
        """Read a file from Puter cloud storage."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/drivers/fs/read",
                    json={"path": path},
                )
                if response.status_code == 200:
                    return response.json().get("content")
        except Exception as e:
            logger.error("Puter read failed: %s", e)
        return None

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email via Puter email service."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/drivers/email",
                    json={"to": to, "subject": subject, "body": body},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Puter email failed: %s", e)
            return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "available": True,
        }
