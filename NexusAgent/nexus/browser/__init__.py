"""NEXUS Browser — Browser automation via micro-service and Playwright."""

__all__ = [
    "BrowserService",
    "PlaywrightExtensions",
]


def __getattr__(name):
    """Lazy import for optional modules."""
    if name == "BrowserService":
        from nexus.browser.browser_service import BrowserService
        return BrowserService
    elif name == "PlaywrightExtensions":
        from nexus.browser.playwright_ext import PlaywrightExtensions
        return PlaywrightExtensions
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
