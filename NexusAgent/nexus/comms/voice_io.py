"""
NEXUS Voice I/O — Speech-to-Text and Text-to-Speech interfaces.

Supports:
  - STT: Whisper API, local Whisper model
  - TTS: OpenAI TTS API, system TTS
  - Voice activity detection
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class VoiceIO:
    """
    Voice I/O manager for NEXUS.

    Usage:
        vio = VoiceIO()
        text = await vio.transcribe(audio_path="recording.wav")
        audio = await vio.synthesize("Hello, how can I help?")
    """

    def __init__(self):
        self.settings = get_settings()

    async def transcribe(
        self,
        audio_path: Optional[str] = None,
        audio_base64: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_path: Path to audio file.
            audio_base64: Base64-encoded audio data.
            language: Language hint (e.g., "en", "fr").

        Returns:
            Transcribed text.
        """
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.settings.openai_api_key)

            if audio_base64:
                # Decode base64 to temp file
                audio_data = base64.b64decode(audio_base64)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_data)
                    audio_path = f.name

            if not audio_path:
                return ""

            with open(audio_path, "rb") as audio_file:
                kwargs = {"model": "whisper-1", "file": audio_file}
                if language:
                    kwargs["language"] = language
                response = await client.audio.transcriptions.create(**kwargs)

            return response.text

        except ImportError:
            logger.warning("OpenAI SDK not available for transcription")
        except Exception as e:
            logger.error("Transcription failed: %s", e)

        return ""

    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize.
            voice: Voice name (alloy, echo, fable, onyx, nova, shimmer).
            model: TTS model (tts-1 or tts-1-hd).
            output_path: Path to save audio file.

        Returns:
            Path to the generated audio file, or None on failure.
        """
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.settings.openai_api_key)

            response = await client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
            )

            if not output_path:
                output_path = os.path.join(
                    tempfile.gettempdir(),
                    f"nexus_tts_{asyncio.get_event_loop().time():.0f}.mp3",
                )

            response.stream_to_file(output_path)
            return output_path

        except ImportError:
            logger.warning("OpenAI SDK not available for TTS")
        except Exception as e:
            logger.error("TTS failed: %s", e)

        return None
