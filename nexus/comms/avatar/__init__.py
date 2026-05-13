"""
NEXUS Avatar Module — AI-powered conversational avatar with VRM/3D rendering.

Powered by AIAvatarKit (github.com/uezo/aiavatarkit) for the Speech-to-Speech
pipeline and VOICEVOX for Japanese anime-style TTS.

Components:
  - AvatarManager: Orchestrates VAD → STT → NEXUS LLM → TTS → LipSync
  - VRMRenderer: Renders VRM avatar models (VRoidHub compatible)
  - VoiceVoxBridge: Japanese anime-style TTS via VOICEVOX/AivisSpeech
  - LipSync: Audio-driven lip movement synchronization
  - FaceController: Facial expression control from LLM output
"""

from nexus.comms.avatar.avatar_manager import AvatarManager
from nexus.comms.avatar.vrm_renderer import VRMRenderer
from nexus.comms.avatar.voicevox_bridge import VoiceVoxBridge, AivisSpeechBridge
from nexus.comms.avatar.lip_sync import LipSyncEngine
from nexus.comms.avatar.face_controller import FaceController

__all__ = [
    "AvatarManager",
    "VRMRenderer",
    "VoiceVoxBridge",
    "AivisSpeechBridge",
    "LipSyncEngine",
    "FaceController",
]
