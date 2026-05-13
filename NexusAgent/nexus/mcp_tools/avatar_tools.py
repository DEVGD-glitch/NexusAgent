"""
NEXUS Avatar MCP Tools — Control the anime avatar from any interface.

These tools are registered as MCP tools and can be called from
the chat, CLI, API, or agent orchestrator.

Tools:
  - avatar_start: Start the avatar window
  - avatar_speak: Text-to-speech with optional expression
  - avatar_set_vrm: Load a VRM model file
  - avatar_set_expression: Set facial expression
  - avatar_list_voices: List available VOICEVOX voices
  - avatar_set_speaker: Change VOICEVOX speaker
  - avatar_start_conversation: Start autonomous voice conversation
"""

from __future__ import annotations

import logging
from typing import Optional

from nexus.comms.avatar import AvatarManager

logger = logging.getLogger(__name__)

# Global avatar instance (singleton, initialized on first use)
_avatar: AvatarManager | None = None


def _get_avatar() -> AvatarManager:
    global _avatar
    if _avatar is None:
        _avatar = AvatarManager()
    return _avatar


async def avatar_start(vrm_path: Optional[str] = None) -> str:
    """Start the avatar in a standalone window."""
    avatar = _get_avatar()
    if vrm_path:
        await avatar.set_vrm(vrm_path)
    await avatar.start()
    return f"Avatar started (VRM: {vrm_path or 'default'})"


async def avatar_speak(text: str, expression: Optional[str] = None) -> str:
    """Synthesize speech with optional facial expression."""
    avatar = _get_avatar()
    if not avatar.is_running:
        await avatar.start()
    audio = await avatar.speak(text, expression=expression)
    return f"Spoke {len(audio)} bytes of audio (expression: {expression or 'neutral'})"


async def avatar_set_vrm(path: str) -> str:
    """Load a VRM model from file path."""
    avatar = _get_avatar()
    await avatar.set_vrm(path)
    return f"VRM model loaded: {path}"


async def avatar_set_expression(name: str) -> str:
    """Set facial expression (neutral, joy, angry, sorrow, fun, surprise, thinking)."""
    avatar = _get_avatar()
    await avatar.set_expression(name)
    return f"Expression set: {name}"


async def avatar_list_voices() -> str:
    """List available VOICEVOX voices."""
    avatar = _get_avatar()
    voices = avatar.get_available_voices()
    lines = [f"  {v['id']}: {v['name']}" for v in voices[:20]]
    return f"Available voices ({len(voices)} total):\n" + "\n".join(lines)


async def avatar_set_speaker(speaker_id: int) -> str:
    """Set VOICEVOX speaker by ID."""
    avatar = _get_avatar()
    await avatar.set_speaker(speaker_id)
    return f"Speaker set to ID {speaker_id}"


async def avatar_start_conversation(api_key: str, system_prompt: str = "You are a helpful anime companion.") -> str:
    """Start autonomous voice conversation via AIAvatarKit."""
    avatar = _get_avatar()
    await avatar.start_aiavatar(api_key=api_key, system_prompt=system_prompt)
    return "AIAvatarKit initialized. Ready for autonomous conversation."


async def avatar_expression_from_text(text: str) -> str:
    """Analyze text sentiment and suggest an expression."""
    from nexus.comms.avatar.face_controller import FaceController
    fc = FaceController()
    clean = fc.extract_face_data(text)
    return f"Expression: {await fc.get()}\nClean text: {clean}"
