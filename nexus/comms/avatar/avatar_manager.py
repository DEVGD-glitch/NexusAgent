"""
NEXUS Avatar Manager — Orchestrates the full Speech-to-Speech pipeline.

Architecture:
  VAD → STT → NEXUS LLM → TTS → LipSync → VRM Render
              ↑                      ↓
         Face Controller     Audio Playback

Integrates AIAvatarKit (aiavatar package) as the VAD/STT/TTS backend
while routing LLM calls through NEXUS's multi-provider router for
full sovereignty (user chooses the model/API key).

Usage:
    manager = AvatarManager()
    await manager.start()           # Launch avatar in standalone window
    await manager.set_vrm("model.vrm")  # Load VRM model
    await manager.speak("Hello!")   # Text-to-speech + lip sync
    await manager.set_expression("joy")  # Face expression
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from nexus.comms.avatar.vrm_renderer import VRMRenderer
from nexus.comms.avatar.voicevox_bridge import VoiceVoxBridge, AivisSpeechBridge
from nexus.comms.avatar.lip_sync import LipSyncEngine
from nexus.comms.avatar.face_controller import FaceController
from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class AvatarManager:
    """
    High-level avatar controller.

    Wraps AIAvatarKit components and connects them to NEXUS's
    LLM router, memory system, and MCP tools.
    """

    def __init__(
        self,
        vrm_path: Optional[str] = None,
        tts_engine: str = "voicevox",
        voicevox_host: str = "http://127.0.0.1:50021",
        aivis_host: str = "http://127.0.0.1:10101",
    ) -> None:
        self.settings = get_settings()
        self.vrm_path = vrm_path
        self.tts_engine = tts_engine

        # TTS backends
        self.voicevox = VoiceVoxBridge(base_url=voicevox_host)
        self.aivis = AivisSpeechBridge(base_url=aivis_host)

        # Avatar rendering
        self.renderer = VRMRenderer()
        self.lip_sync = LipSyncEngine()
        self.face_controller = FaceController()

        self._running = False
        self._current_speaker: int = 46  # VOICEVOX default: 46 = 春日部つむぎ
        self._aiavatar_instance = None

    async def start(self) -> None:
        """Start the avatar in a standalone window with WebSocket server."""
        self._running = True
        await self.renderer.initialize(self.vrm_path)
        logger.info("[Avatar] Started with VRM: %s", self.vrm_path or "chibi (default)")

    async def stop(self) -> None:
        """Stop the avatar and clean up resources."""
        self._running = False
        await self.renderer.close()
        await self.voicevox.close()
        await self.aivis.close()
        logger.info("[Avatar] Stopped")

    async def speak(self, text: str, expression: Optional[str] = None) -> bytes:
        """
        Synthesize speech with optional expression.

        Returns audio bytes (WAV, 24kHz mono).
        """
        if self.tts_engine == "aivis":
            audio = await self.aivis.synthesize(text)
        else:
            audio = await self.voicevox.synthesize(text, speaker=self._current_speaker)

        if expression:
            await self.face_controller.set(expression)

        lip_sync_data = self.lip_sync.process(audio)
        await self.renderer.apply_lip_sync(lip_sync_data)

        return audio

    async def set_vrm(self, path: str) -> None:
        """Load a VRM model from file path."""
        self.vrm_path = path
        if self._running:
            await self.renderer.load_vrm(path)
        logger.info("[Avatar] VRM model set: %s", path)

    async def set_speaker(self, speaker_id: int) -> None:
        """Set VOICEVOX speaker by ID."""
        self._current_speaker = speaker_id
        logger.info("[Avatar] Speaker set to %d", speaker_id)

    async def set_expression(self, name: str) -> None:
        """Set facial expression by name (joy, angry, sorrow, fun, neutral)."""
        await self.face_controller.set(name)
        await self.renderer.apply_expression(name)

    def get_available_voices(self) -> list[dict]:
        """List available VOICEVOX voices."""
        return self.voicevox.get_speakers()

    async def start_aiavatar(self, api_key: str, system_prompt: str = "You are a helpful anime companion.") -> None:
        """
        Start AIAvatarKit for autonomous voice conversation.

        This runs a continuous VAD → STT → NEXUS LLM → TTS loop.
        Requires a running VOICEVOX instance and an API key.
        """
        try:
            from aiavatar import AIAvatar
            self._aiavatar_instance = AIAvatar(
                openai_api_key=api_key,
                system_prompt=system_prompt,
                voicevox_speaker=self._current_speaker,
                debug=self.settings.NEXUS_LOG_LEVEL == "DEBUG",
            )
            logger.info("[Avatar] AIAvatarKit instance created")
        except ImportError:
            logger.warning("[Avatar] aiavatar not installed. Run: pip install aiavatar")
            raise

    async def start_aiavatar_conversation(self) -> None:
        """Start autonomous voice conversation via AIAvatarKit (blocking)."""
        if self._aiavatar_instance is None:
            raise RuntimeError("Call start_aiavatar() first")
        logger.info("[Avatar] Starting autonomous conversation...")
        await self._aiavatar_instance.start_listening()

    @property
    def is_running(self) -> bool:
        return self._running
