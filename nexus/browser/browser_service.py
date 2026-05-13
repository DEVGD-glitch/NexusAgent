"""
NEXUS Browser Service Client — HTTP client for the browser-use micro-service.

Communicates with the isolated browser-use Docker micro-service via HTTP.
This separation avoids dependency conflicts between browser-use (which pins
openai==2.16.0) and other NEXUS dependencies.

Supports:
  - navigate: Go to a URL
  - click: Click an element by selector
  - type: Type text into an element
  - screenshot: Capture a screenshot
  - extract: Extract page content (text + DOM)
  - Both headless and headful browser modes
  - Retry logic with configurable backoff
  - Integration with the MCP server as a tool

Usage:
    from nexus.browser.browser_service import BrowserService

    service = BrowserService()
    result = await service.navigate("https://example.com")
    screenshot = await service.screenshot()
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import BrowserError, BrowserServiceUnavailableError

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class BrowserAction:
    """A browser action to execute."""
    action: str  # navigate, click, type, screenshot, extract
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    wait_seconds: float = 2.0
    headless: bool = True

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"action": self.action, "wait_seconds": self.wait_seconds}
        if self.url:
            d["url"] = self.url
        if self.selector:
            d["selector"] = self.selector
        if self.text:
            d["text"] = self.text
        return d


@dataclass
class BrowserResult:
    """Result from a browser action."""
    success: bool
    action: str
    url: str = ""
    result: str = ""
    error: str = ""
    screenshot_path: Optional[str] = None
    screenshot_base64: Optional[str] = None
    page_content: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "success": self.success,
            "action": self.action,
            "url": self.url,
            "result": self.result,
            "error": self.error,
        }
        if self.screenshot_path:
            d["screenshot_path"] = self.screenshot_path
        if self.page_content:
            d["page_content"] = self.page_content[:5000]
        return d


@dataclass
class ServiceHealth:
    """Health status of the browser micro-service."""
    available: bool = False
    url: str = ""
    response_time_ms: float = 0.0
    error: Optional[str] = None


# ── Browser Service Client ────────────────────────────────────────

class BrowserService:
    """
    HTTP client for the NEXUS browser-use micro-service.

    The browser-use library runs in an isolated Docker container
    (see docker/Dockerfile.browser) to avoid dependency conflicts.
    This client communicates with it via HTTP.

    Features:
      - navigate, click, type, screenshot, extract actions
      - Configurable micro-service URL
      - Retry logic with exponential backoff
      - Headless and headful browser mode support
      - Integration with MCP server as a tool
      - Service health checking

    Usage:
        service = BrowserService()
        result = await service.navigate("https://example.com")
        screenshot = await service.screenshot()
        content = await service.extract()
    """

    def __init__(
        self,
        service_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the browser service client.

        Args:
            service_url: URL of the browser micro-service.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries on failure.
            retry_delay: Base delay between retries (exponential backoff).
        """
        self.settings = get_settings()
        self._service_url = service_url or self.settings.browser_service_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._action_count: int = 0

    @property
    def service_url(self) -> str:
        """Get the browser service URL."""
        return self._service_url

    async def _request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        method: str = "POST",
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the browser service with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/browse").
            payload: Request payload.
            method: HTTP method.

        Returns:
            Response data as a dict.

        Raises:
            BrowserServiceUnavailableError: If the service is unreachable after retries.
        """
        url = f"{self._service_url}{endpoint}"
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    if method == "POST":
                        response = await client.post(url, json=payload)
                    else:
                        response = await client.get(url)

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:
                        # Rate limited — wait longer
                        retry_after = float(response.headers.get("retry-after", "5"))
                        logger.warning("Browser service rate limited, waiting %.0fs", retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status_code >= 500:
                        # Server error — retry
                        last_error = BrowserError(
                            f"Browser service returned HTTP {response.status_code}: {response.text[:200]}"
                        )
                        delay = self._retry_delay * (2 ** attempt)
                        logger.warning(
                            "Browser service error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, self._max_retries, delay, response.status_code,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Client error — don't retry
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text[:500]}",
                        }

            except httpx.ConnectError as e:
                last_error = e
                delay = self._retry_delay * (2 ** attempt)
                logger.warning(
                    "Browser service unreachable (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, self._max_retries, delay, e,
                )
                await asyncio.sleep(delay)

            except httpx.TimeoutException as e:
                last_error = e
                delay = self._retry_delay * (2 ** attempt)
                logger.warning(
                    "Browser service timeout (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, self._max_retries, delay,
                )
                await asyncio.sleep(delay)

            except Exception as e:
                last_error = e
                logger.error("Unexpected browser service error: %s", e)
                break

        raise BrowserServiceUnavailableError(self._service_url)

    async def health_check(self) -> ServiceHealth:
        """
        Check if the browser service is healthy.

        Returns:
            ServiceHealth with availability status.
        """
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._service_url}/health")
                latency = (time.monotonic() - start) * 1000

                if response.status_code == 200:
                    return ServiceHealth(
                        available=True,
                        url=self._service_url,
                        response_time_ms=latency,
                    )
                else:
                    return ServiceHealth(
                        available=False,
                        url=self._service_url,
                        response_time_ms=latency,
                        error=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return ServiceHealth(
                available=False,
                url=self._service_url,
                error=str(e),
            )

    async def navigate(self, url: str, wait_seconds: float = 2.0) -> BrowserResult:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to.
            wait_seconds: Time to wait for page load.

        Returns:
            BrowserResult with navigation outcome.
        """
        self._action_count += 1
        payload = BrowserAction(
            action="navigate",
            url=url,
            wait_seconds=wait_seconds,
        ).to_dict()

        try:
            data = await self._request("/browse", payload)
            return BrowserResult(
                success=data.get("success", False),
                action="navigate",
                url=url,
                result=data.get("result", ""),
                error=data.get("error", ""),
            )
        except BrowserServiceUnavailableError:
            # Fallback: try direct httpx scrape
            return await self._fallback_navigate(url)

    async def click(self, selector: str, url: str = "", wait_seconds: float = 1.0) -> BrowserResult:
        """
        Click an element on the page.

        Args:
            selector: CSS selector for the element.
            url: Current page URL (for context).
            wait_seconds: Time to wait after clicking.

        Returns:
            BrowserResult with click outcome.
        """
        self._action_count += 1
        payload = BrowserAction(
            action="click",
            url=url,
            selector=selector,
            wait_seconds=wait_seconds,
        ).to_dict()

        data = await self._request("/browse", payload)
        return BrowserResult(
            success=data.get("success", False),
            action="click",
            url=url,
            result=data.get("result", ""),
            error=data.get("error", ""),
        )

    async def type_text(
        self,
        selector: str,
        text: str,
        url: str = "",
        wait_seconds: float = 0.5,
    ) -> BrowserResult:
        """
        Type text into an element.

        Args:
            selector: CSS selector for the input element.
            text: Text to type.
            url: Current page URL (for context).
            wait_seconds: Time to wait after typing.

        Returns:
            BrowserResult with type outcome.
        """
        self._action_count += 1
        payload = BrowserAction(
            action="type",
            url=url,
            selector=selector,
            text=text,
            wait_seconds=wait_seconds,
        ).to_dict()

        data = await self._request("/browse", payload)
        return BrowserResult(
            success=data.get("success", False),
            action="type",
            url=url,
            result=data.get("result", ""),
            error=data.get("error", ""),
        )

    async def screenshot(self, url: str = "", full_page: bool = False) -> BrowserResult:
        """
        Take a screenshot of the current page.

        Args:
            url: Current page URL (for context).
            full_page: Whether to capture the full page.

        Returns:
            BrowserResult with screenshot data.
        """
        self._action_count += 1
        payload = BrowserAction(
            action="screenshot",
            url=url,
        ).to_dict()

        if full_page:
            payload["full_page"] = True

        data = await self._request("/browse", payload)
        return BrowserResult(
            success=data.get("success", False),
            action="screenshot",
            url=url,
            result=data.get("result", "Screenshot captured"),
            screenshot_path=data.get("path"),
            error=data.get("error", ""),
        )

    async def extract(self, url: str = "", selector: Optional[str] = None) -> BrowserResult:
        """
        Extract content from the current page.

        Args:
            url: Current page URL (for context).
            selector: Optional CSS selector to extract specific content.

        Returns:
            BrowserResult with extracted page content.
        """
        self._action_count += 1
        payload = BrowserAction(
            action="extract",
            url=url,
            selector=selector,
        ).to_dict()

        data = await self._request("/browse", payload)
        return BrowserResult(
            success=data.get("success", False),
            action="extract",
            url=url,
            result=data.get("result", ""),
            page_content=data.get("content", data.get("result", "")),
            error=data.get("error", ""),
        )

    async def _fallback_navigate(self, url: str) -> BrowserResult:
        """
        Fallback navigation using httpx when browser service is unavailable.

        Args:
            url: URL to fetch.

        Returns:
            BrowserResult with basic page content.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; NEXUS/1.0)"},
                )

                if response.status_code == 200:
                    # Simple HTML to text conversion
                    import re
                    text = response.text
                    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()

                    return BrowserResult(
                        success=True,
                        action="navigate",
                        url=url,
                        result=f"Fetched page (fallback mode, {len(text)} chars)",
                        page_content=text[:50000],
                    )
                else:
                    return BrowserResult(
                        success=False,
                        action="navigate",
                        url=url,
                        error=f"HTTP {response.status_code} (fallback mode)",
                    )
        except Exception as e:
            return BrowserResult(
                success=False,
                action="navigate",
                url=url,
                error=f"Fallback navigation failed: {e}",
            )

    def get_stats(self) -> dict[str, Any]:
        """Get browser service client statistics."""
        return {
            "service_url": self._service_url,
            "timeout": self._timeout,
            "max_retries": self._max_retries,
            "actions_executed": self._action_count,
            "enabled": self.settings.browser_service_enabled,
        }


# ── MCP Tool Integration ──────────────────────────────────────────

async def register_browser_tools(mcp_server) -> None:
    """
    Register browser service tools with an MCP server.

    Args:
        mcp_server: The FastMCP server instance.
    """
    service = BrowserService()

    @mcp_server.tool()
    async def browser_navigate(url: str, wait_seconds: float = 2.0) -> str:
        """
        Navigate to a URL using the browser service.

        Args:
            url: URL to navigate to.
            wait_seconds: Wait time for page load.
        """
        result = await service.navigate(url, wait_seconds=wait_seconds)
        return json.dumps(result.to_dict(), indent=2)

    @mcp_server.tool()
    async def browser_click(selector: str, url: str = "", wait_seconds: float = 1.0) -> str:
        """
        Click an element on a web page.

        Args:
            selector: CSS selector for the element.
            url: Current page URL.
            wait_seconds: Wait time after clicking.
        """
        result = await service.click(selector, url=url, wait_seconds=wait_seconds)
        return json.dumps(result.to_dict(), indent=2)

    @mcp_server.tool()
    async def browser_type(selector: str, text: str, url: str = "") -> str:
        """
        Type text into an element on a web page.

        Args:
            selector: CSS selector for the input element.
            text: Text to type.
            url: Current page URL.
        """
        result = await service.type_text(selector, text, url=url)
        return json.dumps(result.to_dict(), indent=2)

    @mcp_server.tool()
    async def browser_screenshot(url: str = "") -> str:
        """
        Take a screenshot of the current page.

        Args:
            url: Current page URL.
        """
        result = await service.screenshot(url=url)
        return json.dumps(result.to_dict(), indent=2)

    @mcp_server.tool()
    async def browser_extract(url: str = "", selector: str = "") -> str:
        """
        Extract content from a web page.

        Args:
            url: Page URL to extract from.
            selector: Optional CSS selector for specific content.
        """
        result = await service.extract(url=url, selector=selector or None)
        return json.dumps(result.to_dict(), indent=2)

    @mcp_server.tool()
    async def browser_health() -> str:
        """Check browser service health."""
        health = await service.health_check()
        return json.dumps({
            "available": health.available,
            "url": health.url,
            "response_time_ms": round(health.response_time_ms, 2),
            "error": health.error,
        }, indent=2)
