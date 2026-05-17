"""NEXUS — Browser Automation Tool."""
from __future__ import annotations

import httpx
from typing import Optional
from urllib.parse import urlparse


ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_DOMAINS = {"localhost", "127.0.0.1", "169.254.169.254", "metadata.google.internal"}


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL for SSRF protection."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False, f"Scheme '{parsed.scheme}' not allowed"
        if parsed.hostname in BLOCKED_DOMAINS:
            return False, f"Domain '{parsed.hostname}' is blocked"
        if parsed.hostname and (parsed.hostname.startswith("10.") or
                                parsed.hostname.startswith("192.168.") or
                                parsed.hostname.startswith("172.")):
            return False, "Internal network addresses are blocked"
        return True, ""
    except Exception as e:
        return False, str(e)


async def fetch_page(
    url: str,
    timeout: int = 30,
    max_length: int = 50000,
) -> dict:
    """Fetch a web page and return its content."""
    valid, reason = validate_url(url)
    if not valid:
        return {"success": False, "error": reason}

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            content = response.text[:max_length]
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "title": _extract_title(content),
                "content": content,
                "content_length": len(response.text),
                "truncated": len(response.text) > max_length,
            }
    except httpx.TimeoutException:
        return {"success": False, "error": f"Request timed out after {timeout}s"}
    except httpx.HTTPError as e:
        return {"success": False, "error": str(e)}


def _extract_title(html: str) -> str:
    """Extract title from HTML."""
    import re
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    return match.group(1).strip() if match else ""


async def search_web(query: str, limit: int = 5) -> dict:
    """Search the web using a search API."""
    # Placeholder - integrate with a search API
    return {
        "success": False,
        "error": "Web search not configured. Set SERPER_API_KEY or TAVILY_API_KEY",
    }
