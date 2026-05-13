"""
NEXUS Voice API Routes — STT/TTS/LipSync endpoints.

Endpoints:
  POST /voice/transcribe  — Upload audio → get transcription
  POST /voice/synthesize  — Text → get audio bytes + visemes
  GET  /voice/voices      — List available TTS voices
  WebSocket /voice/stream — Real-time voice streaming

All heavy modules (voice_pipeline, etc.) are lazy-loaded to keep
startup fast and memory usage low.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ═══════════════════════════════════════════════════════════════════
# Lazy singleton for VoicePipeline
# ═══════════════════════════════════════════════════════════════════

_voice_pipeline = None


def _get_voice_pipeline():
    """Lazy-load the VoicePipeline singleton."""
    global _voice_pipeline
    if _voice_pipeline is None:
        from nexus.comms.voice_pipeline import VoicePipeline
        _voice_pipeline = VoicePipeline()
        logger.info("[VoiceAPI] VoicePipeline initialized")
    return _voice_pipeline


# ═══════════════════════════════════════════════════════════════════
# Request / Response Models
# ═══════════════════════════════════════════════════════════════════

class TranscribeRequest(BaseModel):
    """Request body for audio transcription."""
    audio_base64: str = Field(..., description="Base64-encoded audio data (WAV or raw PCM)")
    language: str = Field("fr", description="Language code (e.g., fr, en, ja)")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz (for raw PCM)")


class TranscribeResponse(BaseModel):
    """Response for audio transcription."""
    text: str = Field("", description="Transcribed text")
    language: str = Field("", description="Detected/used language")
    duration_ms: float = Field(0.0, description="Processing duration in ms")


class SynthesizeRequest(BaseModel):
    """Request body for text-to-speech synthesis."""
    text: str = Field(..., description="Text to synthesize", min_length=1)
    voice: str = Field("", description="Voice name (e.g., fr-FR-DeniseNeural)")
    engine: str = Field("edge", description="TTS engine: 'edge' or 'voicevox'")
    emotion: str = Field("", description="Emotion hint: joy, sad, angry, calm, excited, thinking")
    language: str = Field("fr", description="Language code for voice auto-selection")
    voicevox_speaker: int = Field(46, description="VoiceVOX speaker ID (only for engine=voicevox)")
    include_visemes: bool = Field(True, description="Whether to include lip-sync viseme data")


class SynthesizeResponse(BaseModel):
    """Response for text-to-speech synthesis."""
    audio_base64: str = Field("", description="Base64-encoded audio data (MP3 for edge, WAV for voicevox)")
    audio_format: str = Field("", description="Audio format: mp3, wav")
    visemes: list[dict] = Field(default_factory=list, description="Lip-sync viseme data")
    voice: str = Field("", description="Voice used for synthesis")
    engine: str = Field("", description="TTS engine used")
    duration_ms: float = Field(0.0, description="Processing duration in ms")


class VoiceInfo(BaseModel):
    """Voice information."""
    name: str = Field("", description="Voice name/ID")
    language: str = Field("", description="Language locale")
    gender: str = Field("", description="Gender: Female, Male")
    engine: str = Field("", description="TTS engine: edge, voicevox")


class VoicesResponse(BaseModel):
    """Response for listing available voices."""
    voices: list[dict] = Field(default_factory=list, description="Available voices")
    engine: str = Field("", description="Current TTS engine")
    count: int = Field(0, description="Number of voices listed")


# ═══════════════════════════════════════════════════════════════════
# POST /voice/transcribe — Upload audio → get transcription
# ═══════════════════════════════════════════════════════════════════

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """
    Transcribe audio to text using the voice pipeline.

    Accepts base64-encoded audio data (WAV or raw PCM).
    Runs VAD (voice activity detection) first, then STT (speech-to-text).
    """
    start = time.monotonic()

    try:
        # Decode base64 audio
        try:
            audio_bytes = base64.b64decode(request.audio_base64)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid base64 audio data. Provide WAV or raw PCM audio encoded in base64.",
            )

        if len(audio_bytes) < 100:
            raise HTTPException(
                status_code=400,
                detail="Audio data too short. Provide at least 100 bytes of audio.",
            )

        pipeline = _get_voice_pipeline()
        pipeline.set_language(request.language)

        # Process: VAD + STT
        text = await pipeline.process_audio_input(audio_bytes)

        latency = (time.monotonic() - start) * 1000
        logger.info(
            "[VoiceAPI] Transcribed %d bytes → '%s' (%.1fms)",
            len(audio_bytes), text[:80], latency,
        )

        return TranscribeResponse(
            text=text,
            language=request.language,
            duration_ms=round(latency, 1),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[VoiceAPI] Transcription failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(exc)[:500]}",
        )


# ═══════════════════════════════════════════════════════════════════
# POST /voice/synthesize — Text → get audio bytes + visemes
# ═══════════════════════════════════════════════════════════════════

@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(request: SynthesizeRequest):
    """
    Synthesize text to speech audio with optional lip-sync viseme data.

    Supports two engines:
      - "edge": Free, multi-language, no server required (default)
      - "voicevox": Anime-style, requires VoiceVOX server at localhost:50021
    """
    start = time.monotonic()

    try:
        pipeline = _get_voice_pipeline()

        # Set engine if different from current
        if request.engine and request.engine != pipeline.voice_engine:
            pipeline.set_voice_engine(request.engine)

        # Override voice if specified
        if request.voice and request.engine == "edge":
            pipeline.edge_tts.default_voice = request.voice

        # Override VoiceVOX speaker if specified
        if request.engine == "voicevox" and request.voicevox_speaker:
            pipeline.voicevox_speaker = request.voicevox_speaker

        # Synthesize: TTS + LipSync
        audio_bytes, visemes = await pipeline.process_text_output(
            text=request.text,
            emotion=request.emotion,
        )

        if not audio_bytes:
            raise HTTPException(
                status_code=500,
                detail="TTS synthesis returned empty audio. Check that the TTS engine is available.",
            )

        # Encode audio as base64
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Determine audio format
        audio_format = "wav"
        if request.engine == "edge":
            audio_format = "mp3"  # EdgeTTS outputs MP3

        # Determine which voice was actually used
        voice_used = request.voice
        if not voice_used:
            if request.engine == "edge":
                voice_used = pipeline.edge_tts.default_voice
            else:
                voice_used = f"voicevox:{request.voicevox_speaker}"

        latency = (time.monotonic() - start) * 1000
        logger.info(
            "[VoiceAPI] Synthesized %d chars → %d bytes, %d visemes (%.1fms, engine=%s)",
            len(request.text), len(audio_bytes), len(visemes), latency, request.engine,
        )

        return SynthesizeResponse(
            audio_base64=audio_b64,
            audio_format=audio_format,
            visemes=visemes if request.include_visemes else [],
            voice=voice_used,
            engine=request.engine,
            duration_ms=round(latency, 1),
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("[VoiceAPI] Synthesis failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Speech synthesis failed: {str(exc)[:500]}",
        )


# ═══════════════════════════════════════════════════════════════════
# GET /voice/voices — List available TTS voices
# ═══════════════════════════════════════════════════════════════════

@router.get("/voices", response_model=VoicesResponse)
async def list_voices(engine: str = "edge", language: str = ""):
    """
    List available TTS voices.

    Args:
        engine: TTS engine to query ("edge" or "voicevox")
        language: Optional language filter (e.g., "fr", "en", "ja")
    """
    try:
        pipeline = _get_voice_pipeline()

        if engine == "voicevox":
            voices = await pipeline.voicevox.get_speakers()
        else:
            voices = await pipeline.edge_tts.list_voices(language=language)

        # Filter by language if specified for voicevox
        if language and engine == "voicevox":
            voices = [v for v in voices if language.lower() in str(v).lower()]

        return VoicesResponse(
            voices=voices,
            engine=engine,
            count=len(voices),
        )

    except Exception as exc:
        logger.error("[VoiceAPI] Failed to list voices: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list voices: {str(exc)[:500]}",
        )


# ═══════════════════════════════════════════════════════════════════
# WebSocket /voice/stream — Real-time voice streaming
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """
    Real-time voice streaming WebSocket.

    Protocol (JSON messages):

    Client → Server:
      {"type": "audio", "data": "<base64_audio>", "language": "fr"}
      {"type": "synthesize", "text": "Hello!", "engine": "edge", "emotion": "joy"}
      {"type": "set_engine", "engine": "edge"}
      {"type": "ping"}

    Server → Client:
      {"type": "transcription", "text": "...", "language": "fr"}
      {"type": "audio", "data": "<base64_audio>", "format": "mp3", "visemes": [...]}
      {"type": "error", "message": "..."}
      {"type": "pong"}
      {"type": "connected"}
    """
    await websocket.accept()
    logger.info("[VoiceAPI] WebSocket client connected for voice streaming")

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "message": "NEXUS Voice Stream ready",
        "engines": ["edge", "voicevox"],
    })

    pipeline = _get_voice_pipeline()

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw)
                msg_type = data.get("type", "")

                # ── Audio input (STT) ──────────────────────────
                if msg_type == "audio":
                    audio_b64 = data.get("data", "")
                    language = data.get("language", "fr")

                    if not audio_b64:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing audio data",
                        })
                        continue

                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        pipeline.set_language(language)
                        text = await pipeline.process_audio_input(audio_bytes)

                        await websocket.send_json({
                            "type": "transcription",
                            "text": text,
                            "language": language,
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Transcription failed: {str(e)[:200]}",
                        })

                # ── Text synthesis (TTS) ───────────────────────
                elif msg_type == "synthesize":
                    text = data.get("text", "")
                    engine = data.get("engine", pipeline.voice_engine)
                    emotion = data.get("emotion", "")

                    if not text:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing text for synthesis",
                        })
                        continue

                    try:
                        # Switch engine if requested
                        if engine != pipeline.voice_engine:
                            pipeline.set_voice_engine(engine)

                        audio_bytes, visemes = await pipeline.process_text_output(
                            text=text,
                            emotion=emotion,
                        )

                        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else ""
                        audio_format = "mp3" if engine == "edge" else "wav"

                        await websocket.send_json({
                            "type": "audio",
                            "data": audio_b64,
                            "format": audio_format,
                            "visemes": visemes,
                            "text": text[:200],
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Synthesis failed: {str(e)[:200]}",
                        })

                # ── Set engine ─────────────────────────────────
                elif msg_type == "set_engine":
                    engine = data.get("engine", "edge")
                    try:
                        pipeline.set_voice_engine(engine)
                        await websocket.send_json({
                            "type": "engine_changed",
                            "engine": engine,
                        })
                    except ValueError as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })

                # ── Ping/Pong ──────────────────────────────────
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message",
                })
            except Exception as e:
                logger.error("[VoiceAPI] Stream message error: %s", e)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Internal error: {str(e)[:200]}",
                    })
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("[VoiceAPI] WebSocket error: %s", e)
    finally:
        logger.info("[VoiceAPI] WebSocket client disconnected from voice stream")
