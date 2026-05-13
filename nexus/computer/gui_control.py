"""
NEXUS GUI Controller — Cross-platform desktop automation.

Provides desktop GUI control via:
  - PyAutoGUI: Cross-platform mouse/keyboard automation
  - AT-SPI (Linux): Accessibility toolkit for UI element access
  - UIAutomation (Windows): Windows UI Automation API

Supports:
  - Mouse control (click, double-click, right-click, drag)
  - Keyboard control (type, hotkey, key press/release)
  - Window management (list, focus, move, resize, close)
  - Screen capture
  - Platform-specific adapters for accessibility

All platform-specific dependencies are lazy-imported to gracefully
handle missing installations.

Usage:
    from nexus.computer.gui_control import GUIController

    gui = GUIController()
    await gui.click(x=100, y=200)
    await gui.type_text("Hello World")
    await gui.hotkey("ctrl", "c")
"""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import NexusError

logger = logging.getLogger(__name__)

# ── Platform Detection ─────────────────────────────────────────────

CURRENT_PLATFORM = platform.system().lower()  # linux, windows, darwin


# ── Exceptions ─────────────────────────────────────────────────────

class GUIError(NexusError):
    """Raised when a GUI operation fails."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="GUI_ERROR", details=details)


# ── Data Structures ────────────────────────────────────────────────

@dataclass
class WindowInfo:
    """Information about a desktop window."""
    title: str
    window_id: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    is_active: bool = False
    process_id: int = 0
    process_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "window_id": self.window_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_active": self.is_active,
            "process_id": self.process_id,
            "process_name": self.process_name,
        }


@dataclass
class UIElement:
    """A UI element discovered via accessibility APIs."""
    name: str
    role: str = ""
    role_type: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    text: str = ""
    is_clickable: bool = False
    is_editable: bool = False
    is_visible: bool = True
    children: list["UIElement"] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "text": self.text[:200],
            "is_clickable": self.is_clickable,
            "is_editable": self.is_editable,
            "center": self.center,
        }


# ── Platform Adapters ──────────────────────────────────────────────

class LinuxATSPIAdapter:
    """
    Linux AT-SPI accessibility adapter.

    Uses python-atspi (via pyatspi or gi) to access UI elements
    on Linux desktops via the Assistive Technology Service Provider.
    """

    def is_available(self) -> bool:
        """Check if AT-SPI is available."""
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi  # noqa: F401
            return True
        except (ImportError, ValueError):
            return False

    async def get_active_window_elements(self) -> list[UIElement]:
        """Get UI elements from the active window via AT-SPI."""
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi

            desktop = Atspi.get_desktop(0)
            elements = []

            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if app is None:
                    continue
                try:
                    for j in range(min(app.get_child_count(), 50)):
                        win = app.get_child_at_index(j)
                        if win and win.get_state_set().contains(Atspi.StateType.ACTIVE):
                            elements.extend(self._parse_atspi_element(win, depth=0))
                except Exception:
                    continue

            return elements[:200]  # Limit results

        except Exception as e:
            logger.warning("AT-SPI element enumeration failed: %s", e)
            return []

    def _parse_atspi_element(self, node: Any, depth: int = 0, max_depth: int = 3) -> list[UIElement]:
        """Recursively parse AT-SPI nodes into UIElement objects."""
        if depth > max_depth:
            return []

        elements = []
        try:
            name = node.get_name() or ""
            role = node.get_role_name() or ""
            extents = node.get_extents(Atspi.CoordType.SCREEN)

            element = UIElement(
                name=name,
                role=role,
                x=extents.x if extents else 0,
                y=extents.y if extents else 0,
                width=extents.width if extents else 0,
                height=extents.height if extents else 0,
                is_clickable=role in ("push button", "link", "menu item"),
                is_editable=role in ("text", "entry", "document text"),
            )
            elements.append(element)

            # Recurse into children
            for i in range(min(node.get_child_count(), 20)):
                child = node.get_child_at_index(i)
                if child:
                    elements.extend(self._parse_atspi_element(child, depth + 1, max_depth))

        except Exception:
            pass

        return elements

    async def list_windows(self) -> list[WindowInfo]:
        """List all windows via AT-SPI."""
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi

            desktop = Atspi.get_desktop(0)
            windows = []

            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if app is None:
                    continue
                try:
                    for j in range(app.get_child_count()):
                        win = app.get_child_at_index(j)
                        if win:
                            extents = win.get_extents(Atspi.CoordType.SCREEN)
                            states = win.get_state_set()
                            is_active = states.contains(Atspi.StateType.ACTIVE)

                            windows.append(WindowInfo(
                                title=win.get_name() or "",
                                window_id=f"{app.get_name()}:{j}",
                                x=extents.x if extents else 0,
                                y=extents.y if extents else 0,
                                width=extents.width if extents else 0,
                                height=extents.height if extents else 0,
                                is_active=is_active,
                                process_name=app.get_name() or "",
                            ))
                except Exception:
                    continue

            return windows

        except Exception as e:
            logger.warning("AT-SPI window listing failed: %s", e)
            return []


class WindowsUIAutomationAdapter:
    """
    Windows UI Automation adapter.

    Uses the uiautomation library (or comtypes) to access UI elements
    on Windows via the UI Automation API.
    """

    def is_available(self) -> bool:
        """Check if UI Automation is available."""
        try:
            import uiautomation as auto  # noqa: F401
            return True
        except ImportError:
            return False

    async def get_active_window_elements(self) -> list[UIElement]:
        """Get UI elements from the active window via UI Automation."""
        try:
            import uiautomation as auto

            window = auto.GetForegroundControl()
            if not window:
                return []

            elements = []
            self._parse_uia_element(window, elements, depth=0)
            return elements[:200]

        except Exception as e:
            logger.warning("UI Automation element enumeration failed: %s", e)
            return []

    def _parse_uia_element(self, control: Any, elements: list[UIElement], depth: int = 0, max_depth: int = 3):
        """Recursively parse UI Automation elements."""
        if depth > max_depth:
            return

        try:
            rect = control.BoundingRectangle
            element = UIElement(
                name=control.Name or "",
                role=control.ControlTypeName or "",
                x=rect.left if rect else 0,
                y=rect.top if rect else 0,
                width=(rect.right - rect.left) if rect else 0,
                height=(rect.bottom - rect.top) if rect else 0,
                is_clickable=control.ControlTypeName in ("ButtonControl", "HyperlinkControl"),
                is_editable=control.ControlTypeName in ("EditControl", "TextControl"),
            )
            elements.append(element)

            for child in control.GetChildren():
                self._parse_uia_element(child, elements, depth + 1, max_depth)

        except Exception:
            pass

    async def list_windows(self) -> list[WindowInfo]:
        """List all windows via UI Automation."""
        try:
            import uiautomation as auto

            windows = []
            root = auto.GetRootControl()
            for win in root.GetChildren():
                try:
                    rect = win.BoundingRectangle
                    windows.append(WindowInfo(
                        title=win.Name or "",
                        window_id=str(win.NativeWindowHandle) if hasattr(win, "NativeWindowHandle") else "",
                        x=rect.left if rect else 0,
                        y=rect.top if rect else 0,
                        width=(rect.right - rect.left) if rect else 0,
                        height=(rect.bottom - rect.top) if rect else 0,
                        is_active=win == auto.GetForegroundControl(),
                    ))
                except Exception:
                    continue
            return windows

        except Exception as e:
            logger.warning("UI Automation window listing failed: %s", e)
            return []


# ── Main GUI Controller ───────────────────────────────────────────

class GUIController:
    """
    Cross-platform desktop GUI controller.

    Provides:
      - Mouse control (click, double-click, right-click, drag)
      - Keyboard control (type, hotkey, key press/release)
      - Window management (list, focus, move, resize, close)
      - Screen capture
      - Platform-specific UI element access via accessibility APIs

    Uses PyAutoGUI as the primary automation library, with
    platform-specific adapters for advanced accessibility features.

    All dependencies are lazy-imported; methods gracefully handle
    the case where automation tools are not installed.

    Usage:
        gui = GUIController()
        await gui.click(x=100, y=200)
        await gui.type_text("Hello World")
        windows = await gui.list_windows()
    """

    def __init__(self):
        self.settings = get_settings()
        self._platform = CURRENT_PLATFORM

        # Initialize platform adapter
        if self._platform == "linux":
            self._adapter = LinuxATSPIAdapter()
        elif self._platform == "windows":
            self._adapter = WindowsUIAutomationAdapter()
        else:
            self._adapter = None  # macOS — limited accessibility support

        self._action_count: int = 0

    # ── Mouse Control ─────────────────────────────────────────────

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
        duration: float = 0.0,
    ) -> bool:
        """
        Click at screen coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Mouse button (left, right, middle).
            clicks: Number of clicks.
            duration: Move duration before click (0 = instant).

        Returns:
            True if successful.
        """
        self._action_count += 1
        try:
            import pyautogui
            pyautogui.click(x=x, y=y, button=button, clicks=clicks, duration=duration)
            logger.debug("Click at (%d, %d) button=%s clicks=%d", x, y, button, clicks)
            return True
        except ImportError:
            logger.error("pyautogui not available for click")
            return False
        except Exception as e:
            logger.error("Click failed: %s", e)
            return False

    async def double_click(self, x: int, y: int) -> bool:
        """Double-click at coordinates."""
        return await self.click(x, y, clicks=2)

    async def right_click(self, x: int, y: int) -> bool:
        """Right-click at coordinates."""
        return await self.click(x, y, button="right")

    async def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
        button: str = "left",
    ) -> bool:
        """
        Drag from one point to another.

        Args:
            start_x: Start X coordinate.
            start_y: Start Y coordinate.
            end_x: End X coordinate.
            end_y: End Y coordinate.
            duration: Drag duration in seconds.
            button: Mouse button to hold.

        Returns:
            True if successful.
        """
        self._action_count += 1
        try:
            import pyautogui
            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(
                end_x - start_x, end_y - start_y,
                duration=duration, button=button,
            )
            return True
        except ImportError:
            logger.error("pyautogui not available for drag")
            return False
        except Exception as e:
            logger.error("Drag failed: %s", e)
            return False

    async def move_mouse(self, x: int, y: int, duration: float = 0.3) -> bool:
        """Move mouse to coordinates."""
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.error("Mouse move failed: %s", e)
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
        except ImportError:
            return False
        except Exception as e:
            logger.error("Scroll failed: %s", e)
            return False

    # ── Keyboard Control ──────────────────────────────────────────

    async def type_text(self, text: str, interval: float = 0.02) -> bool:
        """
        Type text at the current cursor position.

        Args:
            text: Text to type.
            interval: Interval between keystrokes in seconds.

        Returns:
            True if successful.
        """
        self._action_count += 1
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=interval)
            return True
        except ImportError:
            logger.error("pyautogui not available for typing")
            return False
        except Exception as e:
            logger.error("Type text failed: %s", e)
            return False

    async def press_key(self, key: str) -> bool:
        """
        Press a specific key.

        Args:
            key: Key name (e.g., 'enter', 'tab', 'escape', 'f1').

        Returns:
            True if successful.
        """
        try:
            import pyautogui
            pyautogui.press(key)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.error("Key press failed: %s", e)
            return False

    async def hotkey(self, *keys: str) -> bool:
        """
        Press a keyboard shortcut.

        Args:
            *keys: Keys to press in sequence (e.g., hotkey('ctrl', 'c')).

        Returns:
            True if successful.
        """
        self._action_count += 1
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.error("Hotkey failed: %s", e)
            return False

    async def key_down(self, key: str) -> bool:
        """Hold a key down."""
        try:
            import pyautogui
            pyautogui.keyDown(key)
            return True
        except Exception:
            return False

    async def key_up(self, key: str) -> bool:
        """Release a held key."""
        try:
            import pyautogui
            pyautogui.keyUp(key)
            return True
        except Exception:
            return False

    # ── Window Management ─────────────────────────────────────────

    async def list_windows(self) -> list[WindowInfo]:
        """
        List all open windows.

        Uses platform-specific adapters when available, falls back
        to basic enumeration.

        Returns:
            List of WindowInfo objects.
        """
        # Try platform adapter first
        if self._adapter and self._adapter.is_available():
            windows = await self._adapter.list_windows()
            if windows:
                return windows

        # Fallback: basic window listing via wmctrl (Linux) or tasklist
        if self._platform == "linux":
            return await self._list_windows_linux()
        elif self._platform == "windows":
            return await self._list_windows_windows()

        return []

    async def _list_windows_linux(self) -> list[WindowInfo]:
        """List windows on Linux via wmctrl."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wmctrl", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            windows = []
            for line in stdout.decode().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append(WindowInfo(
                        title=parts[3] if len(parts) > 3 else "",
                        window_id=parts[0],
                    ))
            return windows
        except FileNotFoundError:
            logger.debug("wmctrl not available")
            return []
        except Exception as e:
            logger.warning("Linux window listing failed: %s", e)
            return []

    async def _list_windows_windows(self) -> list[WindowInfo]:
        """List windows on Windows via PowerShell."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                "Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object Id, ProcessName, MainWindowTitle",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            windows = []
            for line in stdout.decode().strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("Id"):
                    continue
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    windows.append(WindowInfo(
                        title=parts[2],
                        process_id=int(parts[0]) if parts[0].isdigit() else 0,
                        process_name=parts[1],
                    ))
            return windows
        except Exception as e:
            logger.warning("Windows window listing failed: %s", e)
            return []

    async def focus_window(self, title: str) -> bool:
        """
        Focus a window by its title.

        Args:
            title: Window title (partial match).

        Returns:
            True if the window was focused.
        """
        if self._platform == "linux":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "wmctrl", "-a", title,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0
            except FileNotFoundError:
                return False
        elif self._platform == "windows":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-Command",
                    f"(New-Object -ComObject WScript.Shell).AppActivate('{title}')",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0
            except Exception:
                return False

        return False

    async def close_window(self, title: str) -> bool:
        """Close a window by its title."""
        if self._platform == "linux":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "wmctrl", "-c", title,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0
            except FileNotFoundError:
                return False
        return False

    # ── Screen Capture ────────────────────────────────────────────

    async def capture_screen(self, region: Optional[tuple[int, int, int, int]] = None) -> str:
        """
        Capture a screenshot.

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

            path = tempfile.mktemp(suffix=".png", prefix="nexus_gui_")
            screenshot.save(path)
            return path

        except ImportError:
            logger.error("pyautogui not available for screen capture")
            return ""
        except Exception as e:
            logger.error("Screen capture failed: %s", e)
            return ""

    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions."""
        try:
            import pyautogui
            return pyautogui.size()
        except ImportError:
            return (1920, 1080)

    # ── UI Element Access ─────────────────────────────────────────

    async def get_ui_elements(self) -> list[UIElement]:
        """
        Get UI elements from the active window via accessibility APIs.

        Returns:
            List of UIElement objects.
        """
        if self._adapter and self._adapter.is_available():
            return await self._adapter.get_active_window_elements()

        logger.warning(
            "Accessibility adapter not available on %s. "
            "Install platform-specific accessibility tools for UI element access.",
            self._platform,
        )
        return []

    async def click_element(self, element: UIElement) -> bool:
        """
        Click a UI element by its center coordinates.

        Args:
            element: The UIElement to click.

        Returns:
            True if successful.
        """
        x, y = element.center
        return await self.click(x, y)

    async def type_into_element(self, element: UIElement, text: str) -> bool:
        """
        Type text into a UI element.

        Args:
            element: The target UIElement.
            text: Text to type.

        Returns:
            True if successful.
        """
        if not element.is_editable:
            logger.warning("Element '%s' is not editable", element.name)
            return False

        x, y = element.center
        await self.click(x, y)
        await asyncio.sleep(0.1)  # Brief pause after clicking
        return await self.type_text(text)

    # ── Statistics ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get GUI controller statistics."""
        adapter_info = {}
        if self._adapter:
            adapter_info = {
                "type": type(self._adapter).__name__,
                "available": self._adapter.is_available(),
            }

        return {
            "platform": self._platform,
            "adapter": adapter_info,
            "screen_size": self.get_screen_size(),
            "actions_executed": self._action_count,
        }
