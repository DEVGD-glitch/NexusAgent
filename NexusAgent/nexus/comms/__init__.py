"""
NEXUS Communication Module — Multi-channel I/O, voice pipeline, and avatar.

Components:
  - VoicePipeline: Complete VAD → STT → TTS → LipSync pipeline
  - SileroVAD: Voice Activity Detection (Silero model with fallback)
  - WhisperSTT: Speech-to-Text (OpenAI Whisper API + faster-whisper local)
  - EdgeTTS: Free Text-to-Speech (Microsoft Edge TTS, no API key)
  - VoiceVOXBridge: Anime TTS (VoiceVOX server at localhost:50021)
  - LipSyncExtractor: Audio → Viseme extraction for VRM lip-sync
  - VoiceIO: Legacy voice I/O (kept for backward compatibility)
  - AvatarManager: VRM avatar controller with WebSocket + events
  - ChannelManager: Multi-platform communication adapters
"""

from nexus.comms.voice_pipeline import (
    VoicePipeline,
    SileroVAD,
    WhisperSTT,
    EdgeTTS,
    VoiceVOXBridge,
    LipSyncExtractor,
    EMOTION_VOICE_MAP,
    DEFAULT_VOICES,
)
from nexus.comms.voice_io import VoiceIO

__all__ = [
    "VoicePipeline",
    "SileroVAD",
    "WhisperSTT",
    "EdgeTTS",
    "VoiceVOXBridge",
    "LipSyncExtractor",
    "EMOTION_VOICE_MAP",
    "DEFAULT_VOICES",
    "VoiceIO",
]
