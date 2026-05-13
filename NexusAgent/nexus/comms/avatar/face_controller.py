"""
NEXUS Face Controller — Facial expression management for the avatar.

Expressions are triggered by tags in the LLM response (e.g., [face:joy])
and synchronized with speech synthesis for natural interaction.

Expression mapping:
  - neutral: 🙂 Default relaxed face
  - joy: 😀 Happy, smiling
  - angry: 😠 Frustrated, annoyed
  - sorrow: 😞 Sad, worried
  - fun: 🥳 Excited, playful
  - surprise: 😮 Shocked, amazed
  - thinking: 🤔 Pondering, considering

VRChat support via OSC protocol for metaverse integration.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

EXPRESSION_MAP = {
    "neutral": 0.0,
    "joy": 1.0,
    "angry": 2.0,
    "sorrow": 3.0,
    "fun": 4.0,
    "surprise": 5.0,
    "thinking": 6.0,
}


class FaceController:
    """
    Controls avatar facial expressions.

    Detects [face:name] tags in text, maps them to expression values,
    and applies them to the VRM model via WebSocket.
    """

    def __init__(self):
        self._current: str = "neutral"
        self._pattern = re.compile(r"\[face:(\w+)\]")

    def extract_expressions(self, text: str) -> list[tuple[str, str]]:
        """
        Extract [face:name] tags from text and return (tag, remaining_text) pairs.

        Example:
            "[face:joy]Hello!" → [("joy", "Hello!")]
        """
        parts: list[tuple[str, str]] = []
        last_end = 0
        for match in self._pattern.finditer(text):
            if match.start() > last_end:
                parts.append((self._current, text[last_end:match.start()]))
            parts.append((match.group(1), ""))
            last_end = match.end()
        if last_end < len(text):
            parts.append((self._current, text[last_end:]))
        return parts

    def extract_face_data(self, text: str) -> str:
        """
        Strip [face:name] tags from text and return clean text.

        Also updates current expression from the last tag found.
        """
        last_expr = self._current
        clean = self._pattern.sub("", text)

        for match in self._pattern.finditer(text):
            expr_name = match.group(1)
            if expr_name in EXPRESSION_MAP:
                last_expr = expr_name

        if last_expr != self._current:
            self._current = last_expr

        return clean

    async def set(self, name: str) -> None:
        """Set current expression."""
        if name in EXPRESSION_MAP:
            self._current = name
            logger.debug("[Face] Expression: %s", name)

    async def get(self) -> str:
        return self._current

    def blend_shape_value(self, name: str) -> float:
        """Get blend shape value for a given expression (0.0-1.0)."""
        return EXPRESSION_MAP.get(name, 0.0) / max(EXPRESSION_MAP.values())


class VRChatFaceController(FaceController):
    """
    VRChat expression bridge via OSC protocol.

    Sends expression parameters to VRChat over UDP/OSC for
    avatar integration in VRChat.
    """

    def __init__(self, osc_host: str = "127.0.0.1", osc_port: int = 9000):
        super().__init__()
        self.osc_host = osc_host
        self.osc_port = osc_port
        self._osc_socket = None

    async def set(self, name: str) -> None:
        await super().set(name)
        if self._osc_socket:
            await self._send_osc(f"/avatar/parameters/Expression{self.blend_shape_value(name)}")

    async def _send_osc(self, address: str) -> None:
        try:
            from pythonosc.udp_client import SimpleUDPClient
            client = SimpleUDPClient(self.osc_host, self.osc_port)
            client.send_message(address, 1.0)
        except ImportError:
            logger.debug("[VRChat] python-osc not installed, skipping OSC send")
        except Exception as e:
            logger.warning("[VRChat] OSC error: %s", e)
