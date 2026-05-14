"""
NEXUS VoiceVox Bridge — Japanese anime-style TTS via VOICEVOX/AivisSpeech.

VOICEVOX is a free, open-source Japanese text-to-speech engine with
100+ anime-style voices. Compatible with AIAvatarKit.

AivisSpeech is a higher-quality fork with additional voices.

Requirements:
  - VOICEVOX running at http://127.0.0.1:50021 (download: voicevox.hiroshiba.jp)
  - OR AivisSpeech at http://127.0.0.1:10101 (aivis-project.com)

Usage:
    bridge = VoiceVoxBridge()
    audio = await bridge.synthesize("こんにちは", speaker=46)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class VoiceVoxBridge:
    """
    VOICEVOX TTS engine wrapper.

    Supports 100+ Japanese anime-style voices.
    Default speaker 46 = 春日部つむぎ (Kasukabe Tsumugi).
    """

    def __init__(self, base_url: str = "http://127.0.0.1:50021"):
        self.base_url = base_url.rstrip("/")
        self._speakers_cache: list[dict] | None = None
        self.http_client: httpx.AsyncClient | None = None
        self._available: Optional[bool] = None

    async def is_available(self) -> bool:
        """Check if VoiceVOX server is reachable."""
        if self._available is not None:
            return self._available

        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/version", timeout=3.0)
            self._available = resp.status_code == 200
            if self._available:
                logger.info("[VoiceVox] Server available at %s", self.base_url)
        except Exception:
            self._available = False
            logger.debug("[VoiceVox] Server not available at %s", self.base_url)

        return self._available

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client

    async def synthesize(self, text: str, speaker: int = 46) -> bytes:
        """
        Synthesize text to speech.

        Args:
            text: Japanese text to speak
            speaker: VOICEVOX speaker ID (46 = Tsumugi, 3 = Zundamon, etc.)

        Returns:
            WAV audio bytes (24kHz, mono, 16-bit PCM)
        """
        client = await self._get_client()

        query_resp = await client.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": speaker},
        )
        query_resp.raise_for_status()
        query = query_resp.json()

        synth_resp = await client.post(
            f"{self.base_url}/synthesis",
            params={"speaker": speaker},
            json=query,
        )
        synth_resp.raise_for_status()
        return synth_resp.content

    async def synthesize_mora(
        self, text: str, speaker: int = 46
    ) -> tuple[bytes, list[dict]]:
        """
        Synthesize with mora timing data for lip sync.

        Returns:
            (audio_bytes, mora_data)
        """
        client = await self._get_client()

        query_resp = await client.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": speaker},
        )
        query_resp.raise_for_status()
        query = query_resp.json()

        mora_data = []
        for accent_phrase in query.get("accent_phrases", []):
            for mora in accent_phrase.get("moras", []):
                mora_data.append({
                    "text": mora.get("text", ""),
                    "vowel": mora.get("vowel", ""),
                    "consonant": mora.get("consonant"),
                    "vowel_length": mora.get("vowel_length", 0.0),
                    "consonant_length": mora.get("consonant_length", 0.0),
                    "pitch": mora.get("pitch", 0.0),
                })

        synth_resp = await client.post(
            f"{self.base_url}/synthesis",
            params={"speaker": speaker},
            json=query,
        )
        synth_resp.raise_for_status()
        return synth_resp.content, mora_data

    def get_speakers(self) -> list[dict]:
        """List available speakers with their IDs and names."""
        if self._speakers_cache is not None:
            return self._speakers_cache

        try:
            import httpx as sync_httpx
            resp = sync_httpx.get(f"{self.base_url}/speakers", timeout=5)
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
            self._speakers_cache = sorted(speakers, key=lambda s: s["id"])
            return self._speakers_cache
        except Exception as e:
            logger.warning("[VoiceVox] Failed to fetch speakers: %s", e)
            return [
                {"id": 3, "name": "ずんだもん (あん子)", "speaker_name": "ずんだもん", "style_name": "あん子"},
                {"id": 46, "name": "春日部つむぎ (ノーマル)", "speaker_name": "春日部つむぎ", "style_name": "ノーマル"},
                {"id": 0, "name": "四国めたん (ノーマル)", "speaker_name": "四国めたん", "style_name": "ノーマル"},
            ]

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None


class AivisSpeechBridge(VoiceVoxBridge):
    """
    AivisSpeech TTS engine wrapper.

    Higher-quality fork of VOICEVOX with additional voices.
    API-compatible with VOICEVOX but runs on port 10101 by default.

    Default speaker: 888753761 = Anneli
    """

    def __init__(self, base_url: str = "http://127.0.0.1:10101"):
        super().__init__(base_url)

    async def synthesize(self, text: str, speaker: str = "888753761") -> bytes:
        return await super().synthesize(text, speaker=int(speaker))
