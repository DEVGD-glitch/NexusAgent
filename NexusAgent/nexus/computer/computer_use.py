"""
NEXUS Computer Use — Desktop automation via PyAutoGUI + OCR.

Provides desktop interaction capabilities:
  - Screenshot capture
  - Mouse/keyboard control
  - OCR text extraction
  - Window management
  - Screen reading
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class ComputerUse:
    """
    Desktop automation controller for NEXUS.

    Uses PyAutoGUI for mouse/keyboard control, Pillow for
    screenshots, and Tesseract for OCR.

    Usage:
        cu = ComputerUse()
        screenshot = await cu.take_screenshot()
        text = await cu.read_screen()
        await cu.click(x=100, y=200)
        await cu.type_text("Hello World")
    """

    def __init__(self):
        self.settings = get_settings()
        self._last_screenshot: Optional[str] = None

    async def take_screenshot(self, region: Optional[tuple[int, int, int, int]] = None) -> str:
        """
        Take a screenshot and return the file path.

        Args:
            region: Optional (left, top, width, height) crop region.

        Returns:
            Path to the saved screenshot.
        """
        try:
            import pyautogui

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            path = tempfile.mktemp(suffix=".png", prefix="nexus_screenshot_")
            screenshot.save(path)
            self._last_screenshot = path
            return path

        except ImportError:
            logger.error("pyautogui not available for screenshots")
            return ""

    async def read_screen(self, image_path: Optional[str] = None) -> str:
        """
        Extract text from the screen using OCR.

        Args:
            image_path: Path to image (default: latest screenshot).

        Returns:
            Extracted text.
        """
        try:
            import pytesseract
            from PIL import Image

            path = image_path or self._last_screenshot
            if not path:
                path = await self.take_screenshot()

            if not path or not Path(path).exists():
                return ""

            image = Image.open(path)
            text = pytesseract.image_to_string(image)
            return text.strip()

        except ImportError:
            logger.error("pytesseract/Pillow not available for OCR")
            return ""
        except Exception as e:
            logger.error("OCR failed: %s", e)
            return ""

    async def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
        """Click at screen coordinates."""
        try:
            import pyautogui
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return True
        except Exception as e:
            logger.error("Click failed: %s", e)
            return False

    async def double_click(self, x: int, y: int) -> bool:
        """Double-click at coordinates."""
        return await self.click(x, y, clicks=2)

    async def right_click(self, x: int, y: int) -> bool:
        """Right-click at coordinates."""
        return await self.click(x, y, button="right")

    async def type_text(self, text: str, interval: float = 0.02) -> bool:
        """Type text at the current cursor position."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=interval)
            return True
        except Exception as e:
            logger.error("Type failed: %s", e)
            return False

    async def press_key(self, key: str) -> bool:
        """Press a specific key (e.g., 'enter', 'tab', 'escape')."""
        try:
            import pyautogui
            pyautogui.press(key)
            return True
        except Exception as e:
            logger.error("Key press failed: %s", e)
            return False

    async def hotkey(self, *keys: str) -> bool:
        """Press a keyboard shortcut (e.g., hotkey('ctrl', 'c'))."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error("Hotkey failed: %s", e)
            return False

    async def scroll(self, amount: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Scroll the mouse wheel."""
        try:
            import pyautogui
            kwargs = {"clicks": amount}
            if x is not None and y is not None:
                kwargs["x"] = x
                kwargs["y"] = y
            pyautogui.scroll(**kwargs)
            return True
        except Exception as e:
            logger.error("Scroll failed: %s", e)
            return False

    async def move_mouse(self, x: int, y: int, duration: float = 0.5) -> bool:
        """Move mouse to coordinates with smooth animation."""
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            logger.error("Mouse move failed: %s", e)
            return False

    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> bool:
        """Drag from one point to another."""
        try:
            import pyautogui
            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
            return True
        except Exception as e:
            logger.error("Drag failed: %s", e)
            return False

    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions."""
        try:
            import pyautogui
            return pyautogui.size()
        except ImportError:
            return (1920, 1080)

    def screenshot_to_base64(self, image_path: str) -> str:
        """Convert a screenshot to base64 for API transmission."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e:
            logger.error("Base64 conversion failed: %s", e)
            return ""
