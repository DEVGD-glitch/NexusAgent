"""
NEXUS Voice Pipeline — VAD → STT → LLM → TTS → Lip-Sync
Supports: Silero VAD, OpenAI Whisper STT, Edge TTS (free), VoiceVOX (anime)

Pipeline flow:
  Audio Input → VAD (speech detection) → STT (transcription) → LLM → TTS (synthesis) → LipSync (visemes)

Usage:
    pipeline = VoicePipeline()
    text = await pipeline.process_audio_input(audio_bytes)
    audio, visemes = await pipeline.process_text_output("Bonjour !")
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import struct
import tempfile
import wave
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Silero VAD — Voice Activity Detection
# ═══════════════════════════════════════════════════════════════════

class SileroVAD:
    """
    Voice Activity Detection using the Silero VAD model.

    Detects speech segments in audio for real-time processing.
    Uses torch + silero_vad under the hood; falls back to
    energy-based detection if dependencies are unavailable.

    Usage:
        vad = SileroVAD()
        is_speech = await vad.detect_speech(audio_chunk)
        segments = await vad.get_speech_segments(audio_bytes)
    """

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._model = None
        self._model_loaded = False

    async def _load_model(self) -> bool:
        """Lazy-load the Silero VAD model."""
        if self._model_loaded:
            return self._model is not None

        try:
            import torch
            self._model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            (self._get_speech_timestamps, _, self._read_audio, _, _) = utils
            self._model_loaded = True
            logger.info("[VAD] Silero VAD model loaded successfully")
            return True
        except ImportError:
            logger.warning("[VAD] torch/silero-vad not available, using energy-based fallback")
            self._model_loaded = True
            return False
        except Exception as e:
            logger.warning("[VAD] Failed to load Silero model: %s, using fallback", e)
            self._model_loaded = True
            return False

    async def detect_speech(self, audio_chunk: bytes) -> bool:
        """
        Detect whether an audio chunk contains speech.

        Args:
            audio_chunk: Raw PCM audio bytes (16-bit, mono, 16kHz recommended).

        Returns:
            True if speech is detected, False otherwise.
        """
        has_model = await self._load_model()

        if has_model and self._model is not None:
            try:
                import torch
                # Save to temp WAV for silero
                wav_bytes = self._pcm_to_wav(audio_chunk)
                audio_tensor = self._read_audio(io.BytesIO(wav_bytes))
                if audio_tensor.numel() == 0:
                    return False
                speech_timestamps = self._get_speech_timestamps(
                    audio_tensor, self._model,
                    sampling_rate=self.sample_rate,
                    threshold=self.threshold,
                )
                return len(speech_timestamps) > 0
            except Exception as e:
                logger.debug("[VAD] Silero detection failed, using fallback: %s", e)

        # Fallback: energy-based detection
        return self._energy_based_detect(audio_chunk)

    async def get_speech_segments(self, audio: bytes) -> list[tuple[float, float]]:
        """
        Get speech segments from audio as (start_sec, end_sec) tuples.

        Args:
            audio: Raw PCM audio bytes.

        Returns:
            List of (start_seconds, end_seconds) for each speech segment.
        """
        has_model = await self._load_model()

        if has_model and self._model is not None:
            try:
                wav_bytes = self._pcm_to_wav(audio)
                audio_tensor = self._read_audio(io.BytesIO(wav_bytes))
                if audio_tensor.numel() == 0:
                    return []
                speech_timestamps = self._get_speech_timestamps(
                    audio_tensor, self._model,
                    sampling_rate=self.sample_rate,
                    threshold=self.threshold,
                )
                return [
                    (seg["start"] / self.sample_rate, seg["end"] / self.sample_rate)
                    for seg in speech_timestamps
                ]
            except Exception as e:
                logger.debug("[VAD] Silero segmentation failed, using fallback: %s", e)

        # Fallback: simple energy-based segmentation
        return self._energy_based_segments(audio)

    def _energy_based_detect(self, audio_chunk: bytes) -> bool:
        """Simple energy-based speech detection fallback."""
        try:
            samples = self._bytes_to_samples(audio_chunk)
            if not samples:
                return False
            rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
            # Threshold calibrated for 16-bit PCM normalized to [-1, 1]
            return rms > 0.02
        except Exception:
            return False

    def _energy_based_segments(self, audio: bytes) -> list[tuple[float, float]]:
        """Simple energy-based segmentation fallback."""
        samples = self._bytes_to_samples(audio)
        if not samples:
            return []

        frame_size = self.sample_rate // 20  # 50ms frames
        segments: list[tuple[float, float]] = []
        in_speech = False
        start = 0.0

        for i in range(0, len(samples), frame_size):
            frame = samples[i:i + frame_size]
            if not frame:
                break
            rms = (sum(s * s for s in frame) / len(frame)) ** 0.5
            t = i / self.sample_rate

            if rms > 0.02 and not in_speech:
                in_speech = True
                start = t
            elif rms <= 0.02 and in_speech:
                in_speech = False
                segments.append((start, t))

        if in_speech:
            segments.append((start, len(samples) / self.sample_rate))

        return segments

    def _bytes_to_samples(self, raw: bytes) -> list[float]:
        """Convert raw PCM16 bytes to float samples [-1.0, 1.0]."""
        count = len(raw) // 2
        if count == 0:
            return []
        fmt = "<" + ("h" * count)
        int_samples = struct.unpack(fmt, raw[:count * 2])
        return [s / 32768.0 for s in int_samples]

    def _pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """Convert raw PCM bytes to WAV format in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# WhisperSTT — Speech-to-Text
# ═══════════════════════════════════════════════════════════════════

class WhisperSTT:
    """
    Speech-to-Text with fallback chain:
      1. OpenAI Whisper API (cloud, best quality)
      2. faster-whisper (local, free, good quality)
      3. Basic (silence → empty string)

    Usage:
        stt = WhisperSTT()
        text = await stt.transcribe(audio_bytes, language="fr")
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._faster_whisper_model = None
        self._faster_whisper_loaded = False

    async def transcribe(self, audio: bytes, language: str = "fr") -> str:
        """
        Transcribe audio to text using the best available engine.

        Fallback chain: OpenAI API → faster-whisper → basic.

        Args:
            audio: Raw PCM or WAV audio bytes.
            language: Language code (e.g., "fr", "en", "ja").

        Returns:
            Transcribed text string.
        """
        # Attempt 1: OpenAI Whisper API
        result = await self._transcribe_openai(audio, language)
        if result is not None:
            return result

        # Attempt 2: faster-whisper (local)
        result = await self._transcribe_faster_whisper(audio, language)
        if result is not None:
            return result

        # Attempt 3: basic — return empty
        logger.warning("[STT] All transcription methods failed, returning empty string")
        return ""

    async def _transcribe_openai(self, audio: bytes, language: str) -> Optional[str]:
        """Transcribe using OpenAI Whisper API (cloud)."""
        try:
            from openai import AsyncOpenAI
            settings = get_settings()
            if not settings.openai_api_key:
                return None

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            # Ensure we have WAV format
            wav_bytes = self._ensure_wav(audio)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as audio_file:
                    response = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                    )
                logger.debug("[STT] OpenAI Whisper transcription successful")
                return response.text
            finally:
                import os
                os.unlink(temp_path)

        except ImportError:
            logger.debug("[STT] OpenAI SDK not available")
            return None
        except Exception as e:
            logger.warning("[STT] OpenAI Whisper API failed: %s", e)
            return None

    async def _transcribe_faster_whisper(self, audio: bytes, language: str) -> Optional[str]:
        """Transcribe using faster-whisper (local, free)."""
        try:
            from faster_whisper import WhisperModel

            if not self._faster_whisper_loaded:
                self._faster_whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
                self._faster_whisper_loaded = True
                logger.info("[STT] faster-whisper model loaded (base, CPU)")

            wav_bytes = self._ensure_wav(audio)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_path = f.name

            try:
                segments, info = self._faster_whisper_model.transcribe(
                    temp_path, language=language, beam_size=5,
                )
                text = " ".join(seg.text.strip() for seg in segments)
                logger.debug("[STT] faster-whisper transcription successful")
                return text
            finally:
                import os
                os.unlink(temp_path)

        except ImportError:
            logger.debug("[STT] faster-whisper not installed")
            return None
        except Exception as e:
            logger.warning("[STT] faster-whisper failed: %s", e)
            return None

    def _ensure_wav(self, audio: bytes) -> bytes:
        """Ensure audio is in WAV format. If already WAV, pass through; otherwise convert."""
        if len(audio) > 4 and audio[:4] == b"RIFF":
            return audio  # Already WAV
        # Convert raw PCM to WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio)
        return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# EdgeTTS — Free Text-to-Speech
# ═══════════════════════════════════════════════════════════════════

# Emotion → voice parameter mapping
EMOTION_VOICE_MAP = {
    "joy": {"rate": "+20%", "pitch": "+10Hz"},
    "excited": {"rate": "+30%", "pitch": "+15Hz"},
    "sad": {"rate": "-20%", "pitch": "-10Hz"},
    "angry": {"rate": "+10%", "pitch": "+5Hz"},
    "calm": {"rate": "-10%", "pitch": "-5Hz"},
    "neutral": {"rate": "+0%", "pitch": "+0Hz"},
    "thinking": {"rate": "-15%", "pitch": "-3Hz"},
}

# Popular voices by language
DEFAULT_VOICES = {
    "fr": "fr-FR-DeniseNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ru": "ru-RU-SvetlanaNeural",
}


class EdgeTTS:
    """
    Free Text-to-Speech using Microsoft Edge TTS.

    100% free, no API key required. Supports 100+ voices in 40+ languages.
    Supports emotion mapping: joy → higher pitch, sad → slower rate.

    Usage:
        tts = EdgeTTS()
        audio = await tts.synthesize("Bonjour!", voice="fr-FR-DeniseNeural")
        audio = await tts.synthesize("Hello!", emotion="joy")
    """

    def __init__(self, default_voice: str = "fr-FR-DeniseNeural", sample_rate: int = 24000):
        self.default_voice = default_voice
        self.sample_rate = sample_rate

    async def synthesize(
        self,
        text: str,
        voice: str = "",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        emotion: str = "",
        language: str = "",
    ) -> bytes:
        """
        Synthesize text to speech audio.

        Args:
            text: Text to synthesize.
            voice: Voice name (e.g., "fr-FR-DeniseNeural"). If empty, uses default.
            rate: Speech rate (e.g., "+20%", "-10%").
            pitch: Pitch adjustment (e.g., "+10Hz", "-5Hz").
            emotion: Emotion hint (joy, sad, angry, calm, excited, thinking).
                     Overrides rate/pitch with emotion-mapped values.
            language: Language code to auto-select voice (fr, en, ja, etc.).

        Returns:
            MP3 audio bytes.
        """
        try:
            import edge_tts as _edge_tts
        except ImportError:
            logger.error("[EdgeTTS] edge-tts not installed. Run: pip install edge-tts")
            return b""

        # Resolve voice
        resolved_voice = voice or self.default_voice
        if not voice and language:
            resolved_voice = DEFAULT_VOICES.get(language, self.default_voice)

        # Apply emotion mapping
        resolved_rate = rate
        resolved_pitch = pitch
        if emotion and emotion in EMOTION_VOICE_MAP:
            em = EMOTION_VOICE_MAP[emotion]
            resolved_rate = em.get("rate", rate)
            resolved_pitch = em.get("pitch", pitch)

        try:
            communicate = _edge_tts.Communicate(
                text=text,
                voice=resolved_voice,
                rate=resolved_rate,
                pitch=resolved_pitch,
            )

            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            audio_bytes = buffer.getvalue()
            logger.debug(
                "[EdgeTTS] Synthesized %d chars → %d bytes (voice=%s, rate=%s)",
                len(text), len(audio_bytes), resolved_voice, resolved_rate,
            )
            return audio_bytes

        except Exception as e:
            logger.error("[EdgeTTS] Synthesis failed: %s", e)
            return b""

    async def list_voices(self, language: str = "") -> list[dict]:
        """
        List available voices.

        Args:
            language: Optional language filter (e.g., "fr", "en").

        Returns:
            List of voice dicts with name, language, gender info.
        """
        try:
            import edge_tts as _edge_tts
            voices = await _edge_tts.list_voices()
            result = []
            for v in voices:
                entry = {
                    "name": v["ShortName"],
                    "display_name": v["FriendlyName"],
                    "language": v["Locale"],
                    "gender": v["Gender"],
                }
                if language:
                    if v["Locale"].startswith(language.lower()):
                        result.append(entry)
                else:
                    result.append(entry)
            return result
        except ImportError:
            logger.warning("[EdgeTTS] edge-tts not installed, returning default voice list")
            return [
                {"name": "fr-FR-DeniseNeural", "display_name": "Denise", "language": "fr-FR", "gender": "Female"},
                {"name": "en-US-JennyNeural", "display_name": "Jenny", "language": "en-US", "gender": "Female"},
                {"name": "ja-JP-NanamiNeural", "display_name": "Nanami", "language": "ja-JP", "gender": "Female"},
            ]
        except Exception as e:
            logger.error("[EdgeTTS] Failed to list voices: %s", e)
            return []


# ═══════════════════════════════════════════════════════════════════
# VoiceVOXBridge — Anime TTS
# ═══════════════════════════════════════════════════════════════════

class VoiceVOXBridge:
    """
    Anime-style TTS via VOICEVOX server.

    Connects to a running VOICEVOX instance at localhost:50021.
    Falls back to EdgeTTS if VoiceVOX is not available.

    Usage:
        bridge = VoiceVOXBridge()
        audio = await bridge.synthesize("こんにちは", speaker=46)
    """

    def __init__(self, base_url: str = "http://localhost:50021"):
        self.base_url = base_url.rstrip("/")
        self._http_client = None
        self._available: Optional[bool] = None
        self._fallback_tts = EdgeTTS()

    async def _get_client(self):
        """Lazy-init httpx client."""
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(timeout=30.0)
            except ImportError:
                logger.warning("[VoiceVOX] httpx not available")
                return None
        return self._http_client

    async def is_available(self) -> bool:
        """Check if VoiceVOX server is reachable."""
        if self._available is not None:
            return self._available

        client = await self._get_client()
        if client is None:
            self._available = False
            return False

        try:
            resp = await client.get(f"{self.base_url}/version", timeout=3.0)
            self._available = resp.status_code == 200
            if self._available:
                logger.info("[VoiceVOX] Server available at %s", self.base_url)
        except Exception:
            self._available = False
            logger.debug("[VoiceVOX] Server not available at %s", self.base_url)

        return self._available

    async def synthesize(self, text: str, speaker: int = 46) -> bytes:
        """
        Synthesize text to speech using VoiceVOX.

        Falls back to EdgeTTS if VoiceVOX is not running.

        Args:
            text: Text to synthesize (Japanese text works best).
            speaker: VoiceVOX speaker ID (46 = 春日部つむぎ).

        Returns:
            WAV audio bytes.
        """
        if not await self.is_available():
            logger.info("[VoiceVOX] Not available, falling back to EdgeTTS")
            return await self._fallback_tts.synthesize(text, voice="ja-JP-NanamiNeural")

        client = await self._get_client()
        if client is None:
            return await self._fallback_tts.synthesize(text, voice="ja-JP-NanamiNeural")

        try:
            # Step 1: Create audio query
            query_resp = await client.post(
                f"{self.base_url}/audio_query",
                params={"text": text, "speaker": speaker},
            )
            query_resp.raise_for_status()
            query = query_resp.json()

            # Step 2: Synthesize audio
            synth_resp = await client.post(
                f"{self.base_url}/synthesis",
                params={"speaker": speaker},
                json=query,
            )
            synth_resp.raise_for_status()

            logger.debug("[VoiceVOX] Synthesized %d chars (speaker=%d)", len(text), speaker)
            return synth_resp.content

        except Exception as e:
            logger.warning("[VoiceVOX] Synthesis failed: %s, falling back to EdgeTTS", e)
            self._available = None  # Reset availability for next check
            return await self._fallback_tts.synthesize(text, voice="ja-JP-NanamiNeural")

    async def get_speakers(self) -> list[dict]:
        """List available VoiceVOX speakers."""
        client = await self._get_client()
        if client is None or not await self.is_available():
            return [
                {"id": 3, "name": "ずんだもん (あん子)", "speaker_name": "ずんだもん"},
                {"id": 46, "name": "春日部つむぎ (ノーマル)", "speaker_name": "春日部つむぎ"},
            ]

        try:
            resp = await client.get(f"{self.base_url}/speakers", timeout=5.0)
            resp.raise_for_status()
            speakers = []
            for speaker in resp.json():
                for style in speaker.get("styles", []):
                    speakers.append({
                        "id": style["id"],
                        "name": f"{speaker['name']} ({style['name']})",
                        "speaker_name": speaker["name"],
                        "style_name": style["name"],
                    })
            return sorted(speakers, key=lambda s: s["id"])
        except Exception as e:
            logger.warning("[VoiceVOX] Failed to fetch speakers: %s", e)
            return []

    async def close(self) -> None:
        """Clean up HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ═══════════════════════════════════════════════════════════════════
# LipSyncExtractor — Audio → Visemes
# ═══════════════════════════════════════════════════════════════════

# Phoneme-to-VRM blend shape mapping
PHONEME_TO_VISEME = {
    "a": "AA", "aa": "AA",
    "i": "II", "ih": "II", "iy": "II",
    "u": "UU", "ou": "UU", "uw": "UU",
    "e": "EE", "eh": "EE", "ey": "EE",
    "o": "OO", "oh": "OO", "ow": "OO",
    "m": "UU", "p": "UU", "b": "UU",
    "s": "II", "z": "II", "t": "II", "d": "II", "n": "II",
    "k": "AA", "g": "AA", "h": "AA",
    "r": "OO", "w": "OO", "l": "OO",
    "f": "UU", "v": "UU",
    "th": "EE",
}

# VRM blend shape names for the 5 vowel visemes
VRM_BLENDSHAPES = {
    "AA": "A",
    "II": "I",
    "UU": "U",
    "EE": "E",
    "OO": "O",
}


class LipSyncExtractor:
    """
    Extract visemes from audio for VRM avatar lip-sync.

    Converts audio waveform energy to viseme timing data,
    mapping to the 5 VRM vowel blend shapes (A, I, U, E, O).

    For VoiceVOX, can use mora timing data for precise lip-sync.

    Usage:
        extractor = LipSyncExtractor()
        visemes = extractor.extract_visemes(audio_bytes)
        # [{"viseme": "AA", "start": 0.1, "end": 0.2, "weight": 0.8}, ...]
    """

    def __init__(self, sample_rate: int = 24000, frame_ms: int = 50):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = sample_rate * frame_ms // 1000

    def extract_visemes(self, audio: bytes) -> list[dict]:
        """
        Extract viseme timing data from audio.

        Uses energy-based detection with vowel estimation from
        spectral characteristics (simplified).

        Args:
            audio: WAV or raw PCM audio bytes.

        Returns:
            List of viseme events:
            [{"viseme": "AA", "start": 0.1, "end": 0.2, "weight": 0.8}, ...]
        """
        samples = self._audio_to_samples(audio)
        if not samples:
            return []

        visemes: list[dict] = []
        num_frames = max(1, len(samples) // self.frame_samples)

        for i in range(num_frames):
            start_idx = i * self.frame_samples
            end_idx = min(start_idx + self.frame_samples, len(samples))
            frame = samples[start_idx:end_idx]

            if not frame:
                continue

            # Calculate energy
            energy = sum(s * s for s in frame) / len(frame)
            rms = energy ** 0.5
            normalized = min(1.0, rms * 50.0)

            start_sec = i * self.frame_ms / 1000.0
            end_sec = (i + 1) * self.frame_ms / 1000.0

            if normalized < 0.05:
                # Silence — keep mouth closed
                continue

            # Estimate vowel from spectral shape (simplified)
            viseme = self._estimate_viseme(frame, normalized)
            weight = min(1.0, normalized)

            visemes.append({
                "viseme": viseme,
                "vrm_blendshape": VRM_BLENDSHAPES.get(viseme, "A"),
                "start": round(start_sec, 3),
                "end": round(end_sec, 3),
                "weight": round(weight, 3),
            })

        return visemes

    def extract_visemes_from_mora(self, mora_data: list[dict]) -> list[dict]:
        """
        Extract visemes from VoiceVOX mora timing data (precise).

        Args:
            mora_data: List of mora dicts from VoiceVOX audio_query.

        Returns:
            List of viseme events with precise timing.
        """
        visemes: list[dict] = []
        time_sec = 0.0

        for mora in mora_data:
            consonant = mora.get("consonant")
            consonant_length = mora.get("consonant_length", 0.0)
            vowel = mora.get("vowel", "")
            vowel_length = mora.get("vowel_length", 0.0)

            if consonant and consonant_length > 0:
                viseme_name = PHONEME_TO_VISEME.get(consonant, "AA")
                visemes.append({
                    "viseme": viseme_name,
                    "vrm_blendshape": VRM_BLENDSHAPES.get(viseme_name, "A"),
                    "start": round(time_sec, 3),
                    "end": round(time_sec + consonant_length, 3),
                    "weight": 0.5,
                })
                time_sec += consonant_length

            if vowel and vowel_length > 0:
                viseme_name = PHONEME_TO_VISEME.get(vowel, "AA")
                visemes.append({
                    "viseme": viseme_name,
                    "vrm_blendshape": VRM_BLENDSHAPES.get(viseme_name, "A"),
                    "start": round(time_sec, 3),
                    "end": round(time_sec + vowel_length, 3),
                    "weight": 0.8,
                })
                time_sec += vowel_length

        return visemes

    def _estimate_viseme(self, frame: list[float], energy: float) -> str:
        """
        Estimate the dominant viseme from a frame of audio samples.

        Uses zero-crossing rate as a rough spectral proxy:
        - Low ZCR → voiced → open vowels (AA, OO)
        - High ZCR → fricative → closed shapes (II, UU)
        """
        if not frame or energy < 0.05:
            return "AA"

        # Zero-crossing rate
        crossings = sum(1 for i in range(1, len(frame)) if frame[i] * frame[i - 1] < 0)
        zcr = crossings / max(len(frame) - 1, 1)

        # Simple spectral estimation based on ZCR
        if zcr < 0.1:
            return "AA"  # Low frequency → open vowel
        elif zcr < 0.2:
            return "OO"  # Medium-low → rounded
        elif zcr < 0.3:
            return "EE"  # Medium → mid-open
        elif zcr < 0.45:
            return "UU"  # Higher → pursed
        else:
            return "II"  # Highest → stretched

    def _audio_to_samples(self, audio_bytes: bytes) -> list[float]:
        """Convert WAV or raw PCM bytes to float samples."""
        if len(audio_bytes) > 4 and audio_bytes[:4] == b"RIFF":
            return self._wav_to_samples(audio_bytes)
        return self._raw_to_samples(audio_bytes)

    def _wav_to_samples(self, wav_bytes: bytes) -> list[float]:
        """Parse WAV header and extract samples."""
        if len(wav_bytes) < 44:
            return self._raw_to_samples(wav_bytes)

        try:
            num_channels = struct.unpack_from("<H", wav_bytes, 22)[0]
            sample_width = struct.unpack_from("<H", wav_bytes, 34)[0] // 8
            data_size = struct.unpack_from("<I", wav_bytes, 40)[0]
            data_start = 44  # Standard WAV header size

            # Handle non-standard headers
            if data_size == 0 and len(wav_bytes) > 44:
                data_start = 44

            audio_data = wav_bytes[data_start:]
            samples = []

            if sample_width == 2:
                count = len(audio_data) // 2
                fmt = "<" + ("h" * count)
                int_samples = struct.unpack(fmt, audio_data[:count * 2])
                samples = [s / 32768.0 for s in int_samples[::num_channels]]
            elif sample_width == 1:
                samples = [
                    (b - 128) / 128.0
                    for i, b in enumerate(audio_data)
                    if i % num_channels == 0
                ]

            return samples
        except Exception:
            return self._raw_to_samples(wav_bytes)

    def _raw_to_samples(self, raw_bytes: bytes) -> list[float]:
        """Convert raw PCM16 bytes to float samples."""
        count = len(raw_bytes) // 2
        if count == 0:
            return []
        fmt = "<" + ("h" * count)
        int_samples = struct.unpack(fmt, raw_bytes[:count * 2])
        return [s / 32768.0 for s in int_samples]


# ═══════════════════════════════════════════════════════════════════
# VoicePipeline — Orchestrator
# ═══════════════════════════════════════════════════════════════════

class VoicePipeline:
    """
    Complete voice pipeline orchestrator: VAD → STT → TTS → LipSync.

    Provides a unified interface for processing audio input (voice → text)
    and text output (text → audio + visemes).

    Supports two TTS engines:
      - "edge": EdgeTTS (free, multi-language, no server required)
      - "voicevox": VoiceVOX (anime-style, requires local server)

    Usage:
        pipeline = VoicePipeline(voice_engine="edge")
        text = await pipeline.process_audio_input(audio_bytes)
        audio, visemes = await pipeline.process_text_output("Bonjour !")
    """

    def __init__(
        self,
        voice_engine: str = "edge",
        stt_language: str = "fr",
        edge_voice: str = "fr-FR-DeniseNeural",
        voicevox_speaker: int = 46,
        voicevox_host: str = "http://localhost:50021",
        vad_threshold: float = 0.5,
    ):
        self.voice_engine = voice_engine
        self.stt_language = stt_language
        self.edge_voice = edge_voice
        self.voicevox_speaker = voicevox_speaker

        # Initialize components
        self.vad = SileroVAD(threshold=vad_threshold)
        self.stt = WhisperSTT()
        self.edge_tts = EdgeTTS(default_voice=edge_voice)
        self.voicevox = VoiceVOXBridge(base_url=voicevox_host)
        self.lip_sync = LipSyncExtractor()

        logger.info(
            "[VoicePipeline] Initialized (engine=%s, stt_lang=%s)",
            voice_engine, stt_language,
        )

    async def process_audio_input(self, audio: bytes) -> str:
        """
        Process audio input: VAD (detect speech) → STT (transcribe).

        If no speech is detected, returns an empty string.

        Args:
            audio: Raw PCM or WAV audio bytes.

        Returns:
            Transcribed text, or empty string if no speech detected.
        """
        # Step 1: VAD — check if audio contains speech
        is_speech = await self.vad.detect_speech(audio)
        if not is_speech:
            logger.debug("[VoicePipeline] No speech detected in audio input")
            return ""

        # Step 2: STT — transcribe audio
        text = await self.stt.transcribe(audio, language=self.stt_language)
        logger.info("[VoicePipeline] Transcribed: '%s'", text[:100])
        return text

    async def process_text_output(
        self,
        text: str,
        emotion: str = "",
    ) -> tuple[bytes, list[dict]]:
        """
        Process text output: TTS (synthesize) → LipSync (extract visemes).

        Args:
            text: Text to synthesize.
            emotion: Optional emotion hint (joy, sad, angry, etc.).

        Returns:
            Tuple of (audio_bytes, viseme_data).
        """
        if not text:
            return b"", []

        # Step 1: TTS
        audio = await self._synthesize(text, emotion)
        if not audio:
            return b"", []

        # Step 2: LipSync
        visemes = self.lip_sync.extract_visemes(audio)

        logger.info(
            "[VoicePipeline] Output: %d chars → %d bytes audio, %d visemes",
            len(text), len(audio), len(visemes),
        )
        return audio, visemes

    async def _synthesize(self, text: str, emotion: str = "") -> bytes:
        """Route to the appropriate TTS engine."""
        if self.voice_engine == "voicevox":
            return await self.voicevox.synthesize(text, speaker=self.voicevox_speaker)
        else:
            return await self.edge_tts.synthesize(
                text,
                voice=self.edge_voice,
                emotion=emotion,
                language=self.stt_language,
            )

    def get_available_voices(self) -> list[dict]:
        """
        Get list of available voices for the current engine.

        Returns:
            List of voice dicts with name, language, etc.
        """
        if self.voice_engine == "voicevox":
            # VoiceVOX speakers are fetched async; return cached or defaults
            return [
                {"id": 3, "name": "ずんだもん", "engine": "voicevox"},
                {"id": 46, "name": "春日部つむぎ", "engine": "voicevox"},
                {"id": 0, "name": "四国めたん", "engine": "voicevox"},
            ]
        else:
            return [
                {"name": "fr-FR-DeniseNeural", "language": "fr-FR", "gender": "Female", "engine": "edge"},
                {"name": "fr-FR-HenriNeural", "language": "fr-FR", "gender": "Male", "engine": "edge"},
                {"name": "en-US-JennyNeural", "language": "en-US", "gender": "Female", "engine": "edge"},
                {"name": "en-US-GuyNeural", "language": "en-US", "gender": "Male", "engine": "edge"},
                {"name": "ja-JP-NanamiNeural", "language": "ja-JP", "gender": "Female", "engine": "edge"},
                {"name": "de-DE-KatjaNeural", "language": "de-DE", "gender": "Female", "engine": "edge"},
                {"name": "es-ES-ElviraNeural", "language": "es-ES", "gender": "Female", "engine": "edge"},
                {"name": "zh-CN-XiaoxiaoNeural", "language": "zh-CN", "gender": "Female", "engine": "edge"},
            ]

    async def get_available_voices_async(self) -> list[dict]:
        """Async version that fetches live voice lists."""
        if self.voice_engine == "voicevox":
            return await self.voicevox.get_speakers()
        else:
            return await self.edge_tts.list_voices()

    def set_voice_engine(self, engine: str) -> None:
        """
        Switch the TTS engine.

        Args:
            engine: "edge" or "voicevox"
        """
        if engine not in ("edge", "voicevox"):
            raise ValueError(f"Unknown voice engine: {engine}. Choose 'edge' or 'voicevox'.")
        self.voice_engine = engine
        logger.info("[VoicePipeline] Voice engine set to: %s", engine)

    def set_language(self, language: str) -> None:
        """Set the STT language."""
        self.stt_language = language
        logger.info("[VoicePipeline] STT language set to: %s", language)

    async def close(self) -> None:
        """Clean up resources."""
        await self.voicevox.close()
        logger.info("[VoicePipeline] Closed")
