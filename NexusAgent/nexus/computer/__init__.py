"""NEXUS Computer — Desktop automation, screen understanding, and process management."""

from nexus.computer.computer_use import ComputerUse

__all__ = [
    "ComputerUse",
    "GUIController",
    "ScreenUnderstanding",
    "ProcessManager",
]


def __getattr__(name):
    """Lazy import for optional modules."""
    if name == "GUIController":
        from nexus.computer.gui_control import GUIController
        return GUIController
    elif name == "ScreenUnderstanding":
        from nexus.computer.screen_understanding import ScreenUnderstanding
        return ScreenUnderstanding
    elif name == "ProcessManager":
        from nexus.computer.process_manager import ProcessManager
        return ProcessManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
