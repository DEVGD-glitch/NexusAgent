"""
NEXUS Playwright Extensions — Native browser automation with self-healing selectors.

Provides high-level browser automation patterns built on Playwright,
with features like:
  - Self-healing selectors (CSS → text → role fallback)
  - Screenshot capture and comparison
  - Page content extraction (DOM + text)
  - Cookie and session management
  - Network request interception

Playwright is an optional dependency. When not installed, all methods
gracefully report the missing dependency.

Usage:
    from nexus.browser.playwright_ext import PlaywrightExtensions

    ext = PlaywrightExtensions()
    await ext.start()
    page = await ext.navigate("https://example.com")
    text = await ext.extract_text(page)
    await ext.stop()
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import BrowserError

logger = logging.getLogger(__name__)


# ── Playwright Availability ───────────────────────────────────────

_playwright_available: Optional[bool] = None


def is_playwright_available() -> bool:
    """Check if Playwright is installed."""
    global _playwright_available
    if _playwright_available is None:
        try:
            from playwright.async_api import async_playwright  # noqa: F401
            _playwright_available = True
        except ImportError:
            _playwright_available = False
    return _playwright_available


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class SelectorResult:
    """Result of a self-healing selector attempt."""
    found: bool
    selector_used: str = ""
    method: str = ""  # css, text, role
    element_count: int = 0
    attempts: list[str] = field(default_factory=list)


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture."""
    success: bool
    path: str = ""
    base64_data: str = ""
    size_bytes: int = 0
    hash_md5: str = ""
    error: str = ""


@dataclass
class ContentResult:
    """Result of page content extraction."""
    success: bool
    text: str = ""
    html: str = ""
    title: str = ""
    url: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    error: str = ""


@dataclass
class NetworkLog:
    """Log of a network request."""
    url: str
    method: str
    status: int = 0
    resource_type: str = ""
    timestamp: float = field(default_factory=time.time)


# ── Self-Healing Selector Strategy ───────────────────────────────

class SelectorStrategy:
    """
    Self-healing selector strategy with fallback chain.

    Tries multiple selector strategies in order:
      1. CSS selector (fastest, most specific)
      2. Text content selector (find by visible text)
      3. Role selector (find by ARIA role + name)
      4. Partial text match (contains text)

    If one strategy fails, it automatically tries the next.
    """

    @staticmethod
    async def find_element(page: Any, selector: str) -> SelectorResult:
        """
        Find an element using self-healing selector strategy.

        Args:
            page: Playwright page object.
            selector: Initial selector to try.

        Returns:
            SelectorResult with the outcome.
        """
        attempts = []
        element = None

        # Strategy 1: Direct CSS selector
        try:
            element = await page.query_selector(selector)
            if element:
                elements = await page.query_selector_all(selector)
                count = len(elements)
                return SelectorResult(
                    found=True,
                    selector_used=selector,
                    method="css",
                    element_count=count,
                    attempts=[f"css: {selector} ✓"],
                )
            attempts.append(f"css: {selector} ✗")
        except Exception as e:
            attempts.append(f"css: {selector} ✗ ({e})")

        # Strategy 2: Text content selector
        try:
            element = await page.get_by_text(selector).element_handle()
            if element:
                return SelectorResult(
                    found=True,
                    selector_used=selector,
                    method="text",
                    element_count=1,
                    attempts=attempts + [f"text: '{selector}' ✓"],
                )
            attempts.append(f"text: '{selector}' ✗")
        except Exception as e:
            attempts.append(f"text: '{selector}' ✗ ({e})")

        # Strategy 3: Role selector (common roles)
        common_roles = ["button", "link", "textbox", "checkbox", "radio", "heading"]
        for role in common_roles:
            try:
                locator = page.get_by_role(role, name=selector)
                element = await locator.element_handle()
                if element:
                    return SelectorResult(
                        found=True,
                        selector_used=f"role={role}, name={selector}",
                        method="role",
                        element_count=1,
                        attempts=attempts + [f"role: {role}('{selector}') ✓"],
                    )
            except Exception:
                continue
        attempts.append("role: all roles ✗")

        # Strategy 4: Partial text match
        try:
            partial_locator = page.locator(f"text={selector}")
            count = await partial_locator.count()
            if count > 0:
                return SelectorResult(
                    found=True,
                    selector_used=f"text*={selector}",
                    method="partial_text",
                    element_count=count,
                    attempts=attempts + [f"partial_text: '{selector}' ✓ ({count} matches)"],
                )
            attempts.append(f"partial_text: '{selector}' ✗")
        except Exception as e:
            attempts.append(f"partial_text: '{selector}' ✗ ({e})")

        return SelectorResult(
            found=False,
            selector_used=selector,
            method="none",
            element_count=0,
            attempts=attempts,
        )


# ── Playwright Extensions ─────────────────────────────────────────

class PlaywrightExtensions:
    """
    Playwright extensions for native browser automation.

    Features:
      - Self-healing selectors (CSS → text → role fallback)
      - Screenshot capture and comparison
      - Page content extraction (DOM + text)
      - Cookie and session management
      - Network request interception
      - Headless and headful modes

    Playwright is lazy-imported; all methods gracefully handle
    the case where it is not installed.

    Usage:
        ext = PlaywrightExtensions()
        await ext.start()
        page = await ext.navigate("https://example.com")
        text = await ext.extract_text(page)
        await ext.stop()
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        default_timeout: float = 30000.0,
        screenshot_dir: Optional[str] = None,
    ):
        """
        Initialize Playwright extensions.

        Args:
            headless: Whether to run in headless mode.
            browser_type: Browser to use (chromium, firefox, webkit).
            default_timeout: Default navigation/wait timeout in ms.
            screenshot_dir: Directory for saving screenshots.
        """
        self.settings = get_settings()
        self._headless = headless
        self._browser_type = browser_type
        self._default_timeout = default_timeout
        self._screenshot_dir = screenshot_dir or os.path.join(
            self.settings.nexus_working_dir, "screenshots"
        )

        # Lazy-initialized Playwright objects
        self._playwright = None
        self._browser = None
        self._context = None
        self._network_logs: list[NetworkLog] = []
        self._pages: dict[str, Any] = {}

    async def start(self) -> bool:
        """
        Start the browser instance.

        Returns:
            True if browser started successfully.
        """
        if not is_playwright_available():
            logger.error("Playwright is not installed. Install with: pip install playwright && playwright install")
            return False

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            if self._browser_type == "firefox":
                self._browser = await self._playwright.firefox.launch(headless=self._headless)
            elif self._browser_type == "webkit":
                self._browser = await self._playwright.webkit.launch(headless=self._headless)
            else:
                self._browser = await self._playwright.chromium.launch(headless=self._headless)

            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (compatible; NEXUS/1.0; +https://github.com/nexus)",
            )

            # Set up network interception
            self._context.on("request", self._on_request)
            self._context.on("response", self._on_response)

            logger.info("Playwright browser started (%s, headless=%s)", self._browser_type, self._headless)
            return True

        except Exception as e:
            logger.error("Failed to start Playwright: %s", e)
            return False

    async def stop(self):
        """Stop the browser and clean up resources."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("Error stopping Playwright: %s", e)
        finally:
            self._playwright = None
            self._browser = None
            self._context = None

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> Any:
        """
        Navigate to a URL and return the page.

        Args:
            url: URL to navigate to.
            wait_until: When to consider navigation done (domcontentloaded, load, networkidle).

        Returns:
            Playwright Page object.
        """
        if not self._context:
            if not await self.start():
                raise BrowserError("Cannot start Playwright browser")

        page = await self._context.new_page()
        page.set_default_timeout(self._default_timeout)

        try:
            await page.goto(url, wait_until=wait_until)
            self._pages[url] = page
            return page
        except Exception as e:
            raise BrowserError(f"Navigation failed for {url}: {e}") from e

    async def click(self, page: Any, selector: str) -> SelectorResult:
        """
        Click an element using self-healing selectors.

        Args:
            page: Playwright page.
            selector: CSS selector or text to find and click.

        Returns:
            SelectorResult with the outcome.
        """
        result = await SelectorStrategy.find_element(page, selector)

        if result.found:
            try:
                if result.method == "css":
                    await page.click(result.selector_used)
                elif result.method == "text":
                    await page.get_by_text(selector).click()
                elif result.method == "role":
                    # Parse role and name from selector_used (format: "role=button, name=Submit")
                    role_part, name_part = result.selector_used.split(", ", 1)
                    role = role_part.split("=", 1)[1]
                    name = name_part.split("=", 1)[1]
                    await page.get_by_role(role, name=name).click()
                elif result.method == "partial_text":
                    await page.locator(f"text={selector}").first.click()
            except Exception as e:
                result.found = False
                logger.warning("Click failed for selector '%s': %s", selector, e)

        return result

    async def type_text(self, page: Any, selector: str, text: str, clear: bool = True) -> SelectorResult:
        """
        Type text into an element using self-healing selectors.

        Args:
            page: Playwright page.
            selector: CSS selector or text to find the input.
            text: Text to type.
            clear: Whether to clear existing text first.

        Returns:
            SelectorResult with the outcome.
        """
        result = await SelectorStrategy.find_element(page, selector)

        if result.found:
            try:
                if result.method == "css":
                    if clear:
                        await page.fill(result.selector_used, "")
                    await page.type(result.selector_used, text)
                else:
                    element = await page.get_by_text(selector).element_handle()
                    if element:
                        if clear:
                            await element.fill("")
                        await element.type(text)
            except Exception as e:
                result.found = False
                logger.warning("Type failed for selector '%s': %s", selector, e)

        return result

    async def screenshot(
        self,
        page: Any,
        name: Optional[str] = None,
        full_page: bool = False,
        selector: Optional[str] = None,
    ) -> ScreenshotResult:
        """
        Take a screenshot of the page or an element.

        Args:
            page: Playwright page.
            name: Optional name for the screenshot file.
            full_page: Whether to capture the full page.
            selector: Optional CSS selector to capture a specific element.

        Returns:
            ScreenshotResult with screenshot data.
        """
        try:
            # Ensure screenshot directory exists
            os.makedirs(self._screenshot_dir, exist_ok=True)

            # Generate filename
            if not name:
                name = f"nexus_screenshot_{int(time.time())}"
            filename = f"{name}.png"
            filepath = os.path.join(self._screenshot_dir, filename)

            # Take screenshot
            if selector:
                element = await page.query_selector(selector)
                if element:
                    await element.screenshot(path=filepath)
                else:
                    return ScreenshotResult(success=False, error=f"Element not found: {selector}")
            else:
                await page.screenshot(path=filepath, full_page=full_page)

            # Read and encode
            with open(filepath, "rb") as f:
                data = f.read()

            md5_hash = hashlib.md5(data).hexdigest()
            b64 = base64.b64encode(data).decode()

            return ScreenshotResult(
                success=True,
                path=filepath,
                base64_data=b64,
                size_bytes=len(data),
                hash_md5=md5_hash,
            )

        except Exception as e:
            return ScreenshotResult(success=False, error=str(e))

    async def screenshot_compare(
        self,
        page: Any,
        reference_path: str,
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        """
        Compare current page with a reference screenshot.

        Args:
            page: Playwright page.
            reference_path: Path to the reference screenshot.
            threshold: Acceptable difference ratio (0.0 to 1.0).

        Returns:
            Dict with comparison results.
        """
        try:
            # Take current screenshot
            current = await self.screenshot(page, name="comparison_current")
            if not current.success:
                return {"match": False, "error": current.error}

            # Simple size-based comparison (for pixel comparison, use pixelmatch)
            ref_size = os.path.getsize(reference_path) if os.path.exists(reference_path) else 0
            size_diff = abs(current.size_bytes - ref_size) / max(ref_size, 1)

            return {
                "match": size_diff <= threshold,
                "size_diff_ratio": round(size_diff, 4),
                "current_size": current.size_bytes,
                "reference_size": ref_size,
                "current_path": current.path,
                "reference_path": reference_path,
            }
        except Exception as e:
            return {"match": False, "error": str(e)}

    async def extract_text(self, page: Any) -> ContentResult:
        """
        Extract text content from the page.

        Args:
            page: Playwright page.

        Returns:
            ContentResult with extracted text.
        """
        try:
            text = await page.inner_text("body")
            title = await page.title()
            url = page.url

            return ContentResult(
                success=True,
                text=text,
                title=title,
                url=url,
            )
        except Exception as e:
            return ContentResult(success=False, error=str(e))

    async def extract_content(self, page: Any) -> ContentResult:
        """
        Extract full content from the page (text, HTML, links, images).

        Args:
            page: Playwright page.

        Returns:
            ContentResult with all extracted content.
        """
        try:
            text = await page.inner_text("body")
            html = await page.content()
            title = await page.title()
            url = page.url

            # Extract links using native locator API
            links = await page.locator('a').evaluate_all(
                "els => els.map(a => ({href: a.href, text: a.textContent.trim()}))"
            )

            # Extract images using native locator API
            images = await page.locator('img').evaluate_all(
                "els => els.map(img => ({src: img.src, alt: img.alt || '', width: img.naturalWidth, height: img.naturalHeight}))"
            )

            return ContentResult(
                success=True,
                text=text,
                html=html,
                title=title,
                url=url,
                links=links or [],
                images=images or [],
            )
        except Exception as e:
            return ContentResult(success=False, error=str(e))

    async def get_cookies(self, page: Any) -> list[dict[str, Any]]:
        """
        Get all cookies for the current page.

        Args:
            page: Playwright page.

        Returns:
            List of cookie dicts.
        """
        if not self._context:
            return []
        try:
            cookies = await self._context.cookies()
            return cookies
        except Exception as e:
            logger.error("Failed to get cookies: %s", e)
            return []

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> bool:
        """
        Set cookies for the browser context.

        Args:
            cookies: List of cookie dicts.

        Returns:
            True if successful.
        """
        if not self._context:
            return False
        try:
            await self._context.add_cookies(cookies)
            return True
        except Exception as e:
            logger.error("Failed to set cookies: %s", e)
            return False

    async def clear_cookies(self) -> bool:
        """Clear all cookies from the browser context."""
        if not self._context:
            return False
        try:
            await self._context.clear_cookies()
            return True
        except Exception as e:
            logger.error("Failed to clear cookies: %s", e)
            return False

    def _on_request(self, request: Any):
        """Handle request events for network logging."""
        self._network_logs.append(NetworkLog(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
        ))

    def _on_response(self, response: Any):
        """Handle response events for network logging."""
        # Update the matching request log with status
        for log in reversed(self._network_logs):
            if log.url == response.url and log.status == 0:
                log.status = response.status
                break

    def get_network_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent network request logs."""
        return [
            {
                "url": log.url[:200],
                "method": log.method,
                "status": log.status,
                "resource_type": log.resource_type,
            }
            for log in self._network_logs[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get Playwright extensions statistics."""
        return {
            "playwright_available": is_playwright_available(),
            "browser_type": self._browser_type,
            "headless": self._headless,
            "is_running": self._browser is not None,
            "pages_open": len(self._pages),
            "network_logs": len(self._network_logs),
            "screenshot_dir": self._screenshot_dir,
        }
