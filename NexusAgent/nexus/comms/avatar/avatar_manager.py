"""
NEXUS Avatar Manager — Orchestrates the full Speech-to-Speech pipeline.

Architecture:
  VAD → STT → NEXUS LLM → TTS → LipSync → VRM Render
              ↑                      ↓
         Face Controller     Audio Playback
         WebSocket Control ← → Connected Clients

Integrates AIAvatarKit (aiavatar package) as the VAD/STT/TTS backend
while routing LLM calls through NEXUS's multi-provider router for
full sovereignty (user chooses the model/API key).

Features:
  - Expression commands via WebSocket
  - Lip-sync viseme data streamed to connected clients
  - Avatar state tracking (current expression, speaking, thinking)
  - Event emission: avatar_expression_change, avatar_speaking_start, avatar_speaking_end

Usage:
    manager = AvatarManager()
    await manager.start()           # Launch avatar in standalone window
    await manager.set_vrm("model.vrm")  # Load VRM model
    await manager.speak("Hello!")   # Text-to-speech + lip sync
    await manager.set_expression("joy")  # Face expression

WebSocket commands:
    {"type": "set_expression", "name": "joy"}
    {"type": "set_vrm", "path": "model.vrm"}
    {"type": "set_speaker", "id": 46}
    {"type": "speak", "text": "Hello!"}
    {"type": "stop_speaking"}
    {"type": "get_state"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from nexus.comms.avatar.vrm_renderer import VRMRenderer
from nexus.comms.avatar.voicevox_bridge import VoiceVoxBridge, AivisSpeechBridge
from nexus.comms.avatar.lip_sync import LipSyncEngine
from nexus.comms.avatar.face_controller import FaceController
from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Avatar State
# ═══════════════════════════════════════════════════════════════════

class AvatarStatus(str, Enum):
    """Avatar status states."""
    IDLE = "idle"
    SPEAKING = "speaking"
    THINKING = "thinking"
    LISTENING = "listening"
    ERROR = "error"


@dataclass
class AvatarState:
    """Tracks the current state of the avatar."""
    status: AvatarStatus = AvatarStatus.IDLE
    current_expression: str = "neutral"
    is_speaking: bool = False
    is_thinking: bool = False
    current_text: str = ""
    current_speaker_id: int = 46
    vrm_path: Optional[str] = None
    last_expression_change: float = 0.0
    last_speech_start: float = 0.0
    last_speech_end: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "current_expression": self.current_expression,
            "is_speaking": self.is_speaking,
            "is_thinking": self.is_thinking,
            "current_text": self.current_text,
            "current_speaker_id": self.current_speaker_id,
            "vrm_path": self.vrm_path,
        }


# ═══════════════════════════════════════════════════════════════════
# Avatar Manager
# ═══════════════════════════════════════════════════════════════════

class AvatarManager:
    """
    High-level avatar controller with WebSocket support and state tracking.

    Wraps AIAvatarKit components and connects them to NEXUS's
    LLM router, memory system, and MCP tools.

    Events emitted:
      - avatar_expression_change: When facial expression changes
      - avatar_speaking_start: When TTS synthesis begins
      - avatar_speaking_end: When TTS playback finishes
    """

    def __init__(
        self,
        vrm_path: Optional[str] = None,
        tts_engine: str = "voicevox",
        voicevox_host: str = "http://127.0.0.1:50021",
        aivis_host: str = "http://127.0.0.1:10101",
    ) -> None:
        self.settings = get_settings()
        self.tts_engine = tts_engine

        # TTS backends
        self.voicevox = VoiceVoxBridge(base_url=voicevox_host)
        self.aivis = AivisSpeechBridge(base_url=aivis_host)

        # Avatar rendering
        self.renderer = VRMRenderer()
        self.lip_sync = LipSyncEngine()
        self.face_controller = FaceController()

        # State tracking
        self._state = AvatarState(vrm_path=vrm_path)
        self._running = False
        self._current_speaker: int = 46  # VOICEVOX default: 46 = 春日部つむぎ
        self._aiavatar_instance = None

        # WebSocket clients for real-time viseme/expression streaming
        self._ws_clients: set = set()

        # Event listeners (callback functions)
        self._event_listeners: dict[str, list] = {
            "avatar_expression_change": [],
            "avatar_speaking_start": [],
            "avatar_speaking_end": [],
        }

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the avatar in a standalone window with WebSocket server."""
        self._running = True
        await self.renderer.initialize(self._state.vrm_path)
        logger.info("[Avatar] Started with VRM: %s", self._state.vrm_path or "chibi (default)")

    async def stop(self) -> None:
        """Stop the avatar and clean up resources."""
        self._running = False
        self._state.status = AvatarStatus.IDLE
        self._state.is_speaking = False
        self._state.is_thinking = False

        # Close all WebSocket clients
        for ws in list(self._ws_clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._ws_clients.clear()

        await self.renderer.close()
        await self.voicevox.close()
        await self.aivis.close()
        logger.info("[Avatar] Stopped")

    # ── Speech ─────────────────────────────────────────────────────

    async def speak(self, text: str, expression: Optional[str] = None) -> bytes:
        """
        Synthesize speech with optional expression.

        Emits:
          - avatar_speaking_start at the beginning
          - avatar_speaking_end when synthesis is complete

        Returns audio bytes (WAV, 24kHz mono).
        """
        if self._state.is_speaking:
            logger.warning("[Avatar] Already speaking, ignoring new speak request")
            return b""

        # Update state
        self._state.is_speaking = True
        self._state.status = AvatarStatus.SPEAKING
        self._state.current_text = text
        self._state.last_speech_start = time.time()

        # Emit speaking start event
        await self._emit_event("avatar_speaking_start", {
            "text": text[:200],
            "expression": expression,
            "speaker_id": self._current_speaker,
        })

        # Notify WebSocket clients
        await self._broadcast_to_clients({
            "type": "speaking_start",
            "text": text[:200],
            "expression": expression,
        })

        try:
            # Set expression if provided
            if expression:
                await self.set_expression(expression)

            # Synthesize audio
            if self.tts_engine == "aivis":
                audio = await self.aivis.synthesize(text)
            else:
                audio = await self.voicevox.synthesize(text, speaker=self._current_speaker)

            # Generate lip-sync data
            lip_sync_data = self.lip_sync.process(audio)

            # Apply lip-sync to renderer
            await self.renderer.apply_lip_sync(lip_sync_data)

            # Stream viseme data to WebSocket clients
            await self._broadcast_to_clients({
                "type": "lip_sync",
                "visemes": lip_sync_data,
            })

            return audio

        finally:
            # Update state
            self._state.is_speaking = False
            self._state.status = AvatarStatus.IDLE
            self._state.current_text = ""
            self._state.last_speech_end = time.time()

            # Emit speaking end event
            await self._emit_event("avatar_speaking_end", {
                "text": text[:200],
                "duration_ms": int((time.time() - self._state.last_speech_start) * 1000),
            })

            # Notify WebSocket clients
            await self._broadcast_to_clients({
                "type": "speaking_end",
            })

    async def stop_speaking(self) -> None:
        """Interrupt current speech."""
        self._state.is_speaking = False
        self._state.status = AvatarStatus.IDLE
        self._state.current_text = ""
        await self._broadcast_to_clients({"type": "speaking_end"})
        logger.info("[Avatar] Speech interrupted")

    # ── Expressions ────────────────────────────────────────────────

    async def set_expression(self, name: str) -> None:
        """
        Set facial expression by name.

        Valid names: joy, angry, sorrow, fun, neutral, surprise, thinking.

        Emits: avatar_expression_change
        """
        previous = self._state.current_expression
        if previous == name:
            return

        await self.face_controller.set(name)
        await self.renderer.apply_expression(name)

        self._state.current_expression = name
        self._state.last_expression_change = time.time()

        # If thinking expression, update status
        if name == "thinking":
            self._state.is_thinking = True
            self._state.status = AvatarStatus.THINKING
        elif self._state.is_thinking and name != "thinking":
            self._state.is_thinking = False
            if not self._state.is_speaking:
                self._state.status = AvatarStatus.IDLE

        # Emit expression change event
        await self._emit_event("avatar_expression_change", {
            "previous": previous,
            "current": name,
        })

        # Notify WebSocket clients
        await self._broadcast_to_clients({
            "type": "expression_change",
            "previous": previous,
            "current": name,
        })

        logger.debug("[Avatar] Expression: %s → %s", previous, name)

    # ── VRM Model ──────────────────────────────────────────────────

    async def set_vrm(self, path: str) -> None:
        """Load a VRM model from file path."""
        self._state.vrm_path = path
        if self._running:
            await self.renderer.load_vrm(path)
        await self._broadcast_to_clients({"type": "vrm_loaded", "path": path})
        logger.info("[Avatar] VRM model set: %s", path)

    # ── Voice Settings ─────────────────────────────────────────────

    async def set_speaker(self, speaker_id: int) -> None:
        """Set VOICEVOX speaker by ID."""
        self._current_speaker = speaker_id
        self._state.current_speaker_id = speaker_id
        await self._broadcast_to_clients({"type": "speaker_changed", "speaker_id": speaker_id})
        logger.info("[Avatar] Speaker set to %d", speaker_id)

    def get_available_voices(self) -> list[dict]:
        """List available VOICEVOX voices."""
        return self.voicevox.get_speakers()

    # ── State ──────────────────────────────────────────────────────

    def get_state(self) -> dict[str, Any]:
        """Get current avatar state as a dict."""
        return self._state.to_dict()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_speaking(self) -> bool:
        return self._state.is_speaking

    @property
    def current_expression(self) -> str:
        return self._state.current_expression

    # ── WebSocket Client Management ────────────────────────────────

    def register_ws_client(self, websocket) -> None:
        """Register a WebSocket client for real-time updates."""
        self._ws_clients.add(websocket)
        logger.info("[Avatar] WebSocket client registered (total: %d)", len(self._ws_clients))

    def unregister_ws_client(self, websocket) -> None:
        """Unregister a WebSocket client."""
        self._ws_clients.discard(websocket)
        logger.info("[Avatar] WebSocket client unregistered (total: %d)", len(self._ws_clients))

    async def handle_ws_message(self, websocket, message: str) -> None:
        """
        Handle an incoming WebSocket message from a client.

        Supported commands:
          - set_expression: {"type": "set_expression", "name": "joy"}
          - set_vrm: {"type": "set_vrm", "path": "model.vrm"}
          - set_speaker: {"type": "set_speaker", "id": 46}
          - speak: {"type": "speak", "text": "Hello!"}
          - stop_speaking: {"type": "stop_speaking"}
          - get_state: {"type": "get_state"}
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "set_expression":
                await self.set_expression(data.get("name", "neutral"))

            elif msg_type == "set_vrm":
                await self.set_vrm(data.get("path", ""))

            elif msg_type == "set_speaker":
                await self.set_speaker(int(data.get("id", 46)))

            elif msg_type == "speak":
                text = data.get("text", "")
                expression = data.get("expression")
                if text:
                    await self.speak(text, expression=expression)

            elif msg_type == "stop_speaking":
                await self.stop_speaking()

            elif msg_type == "get_state":
                await self._send_to_client(websocket, {
                    "type": "state",
                    **self._state.to_dict(),
                })

            else:
                await self._send_to_client(websocket, {
                    "type": "error",
                    "message": f"Unknown command: {msg_type}",
                })

        except json.JSONDecodeError:
            await self._send_to_client(websocket, {
                "type": "error",
                "message": "Invalid JSON message",
            })
        except Exception as e:
            logger.error("[Avatar] WebSocket message handling failed: %s", e)
            await self._send_to_client(websocket, {
                "type": "error",
                "message": str(e)[:200],
            })

    async def _broadcast_to_clients(self, data: dict) -> None:
        """Send data to all connected WebSocket clients."""
        message = json.dumps(data)
        disconnected = set()

        for ws in self._ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)

        # Clean up disconnected clients
        self._ws_clients -= disconnected

    async def _send_to_client(self, websocket, data: dict) -> None:
        """Send data to a specific WebSocket client."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            self._ws_clients.discard(websocket)

    # ── Event System ───────────────────────────────────────────────

    def on(self, event_name: str, callback) -> None:
        """
        Register an event listener.

        Supported events:
          - avatar_expression_change
          - avatar_speaking_start
          - avatar_speaking_end
        """
        if event_name in self._event_listeners:
            self._event_listeners[event_name].append(callback)
        else:
            logger.warning("[Avatar] Unknown event: %s", event_name)

    def off(self, event_name: str, callback) -> None:
        """Remove an event listener."""
        if event_name in self._event_listeners:
            self._event_listeners[event_name] = [
                cb for cb in self._event_listeners[event_name] if cb != callback
            ]

    async def _emit_event(self, event_name: str, data: dict) -> None:
        """Emit an event to all registered listeners."""
        if event_name not in self._event_listeners:
            return

        # Also broadcast to NEXUS EventBroadcaster
        try:
            from nexus.core.events import get_broadcaster
            broadcaster = get_broadcaster()
            await broadcaster.broadcast(event_name, data)
        except Exception:
            pass  # Broadcaster might not be available

        # Call local listeners
        for callback in self._event_listeners.get(event_name, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.warning("[Avatar] Event listener error (%s): %s", event_name, e)

    # ── AIAvatarKit Integration ────────────────────────────────────

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
