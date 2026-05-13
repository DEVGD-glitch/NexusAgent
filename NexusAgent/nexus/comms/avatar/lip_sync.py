"""
NEXUS LipSync Engine — Audio-driven lip movement synchronization.

Converts audio waveform to viseme data for VRM avatar mouth movement.

Supports two modes:
  1. Real-time: Process audio chunks as they come (for streaming TTS)
  2. Pre-processed: Full audio to viseme sequence (for pre-generated TTS)

Viseme mapping to VRM blend shapes:
  - aa (a sound): mouth open wide
  - ih (i sound): mouth stretched sideways
  - ou (u sound): mouth pursed
  - eh (e sound): mouth medium open
  - oh (o sound): mouth rounded
  - silence: closed
"""

from __future__ import annotations

import logging
import math
import struct
from typing import Optional

logger = logging.getLogger(__name__)

# Viseme mapping: phoneme → (start, duration, vowel, intensity)
VISEME_MAP = {
    "a": ("aa", "a"),
    "i": ("ih", "i"),
    "u": ("ou", "u"),
    "e": ("eh", "e"),
    "o": ("oh", "o"),
    "k": ("aa", None),
    "s": ("ih", None),
    "t": ("ih", None),
    "n": ("ih", None),
    "h": ("aa", None),
    "m": ("ou", None),
    "r": ("ou", None),
    "w": ("ou", None),
    "p": ("ou", None),
    "b": ("ou", None),
}


class LipSyncEngine:
    """
    Converts audio to viseme timing data for lip sync.
    """

    def __init__(self, sample_rate: int = 24000, frame_ms: int = 50):
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        self.frame_ms = frame_ms

    def process(self, audio_bytes: bytes) -> list[dict]:
        """
        Process WAV audio and generate viseme timing data.

        Uses energy-based detection per frame to estimate mouth opening.

        Returns:
            List of viseme events:
            [{"start_ms": 0, "duration_ms": 50, "vowel": "aa", "value": 0.8}, ...]
        """
        try:
            samples = self._wav_to_samples(audio_bytes)
        except Exception:
            samples = self._raw_to_samples(audio_bytes)

        visemes: list[dict] = []
        num_frames = max(1, len(samples) // self.frame_samples)

        for i in range(num_frames):
            start = i * self.frame_samples
            end = min(start + self.frame_samples, len(samples))
            frame = samples[start:end]

            energy = self._frame_energy(frame)
            rms = math.sqrt(energy / max(len(frame), 1))
            normalized = min(1.0, rms * 50.0)

            # Determine viseme from RMS energy
            if normalized < 0.05:
                viseme_name = "silence"
                vowel = None
                value = 0.0
            elif normalized < 0.2:
                viseme_name = "oh"
                vowel = "o"
                value = normalized * 1.5
            elif normalized < 0.4:
                viseme_name = "aa"
                vowel = "a"
                value = normalized
            else:
                viseme_name = "aa"
                vowel = "a"
                value = min(1.0, normalized)

            visemes.append({
                "start_ms": i * self.frame_ms,
                "duration_ms": self.frame_ms,
                "vowel": vowel,
                "name": viseme_name,
                "value": round(value, 3),
            })

        return visemes

    def process_with_phonemes(self, mora_data: list[dict]) -> list[dict]:
        """
        Generate visemes from VOICEVOX mora timing data.

        More accurate than energy-based detection since it uses
        the actual phoneme timing from the TTS engine.

        Args:
            mora_data: List from VoiceVoxBridge.synthesize_mora()

        Returns:
            List of viseme events with precise timing
        """
        visemes: list[dict] = []
        time_ms = 0.0

        for mora in mora_data:
            consonant = mora.get("consonant")
            consonant_length = mora.get("consonant_length", 0.0)
            vowel = mora.get("vowel", "")
            vowel_length = mora.get("vowel_length", 0.0)

            if consonant and consonant_length > 0:
                viseme_name, _ = VISEME_MAP.get(consonant, ("aa", None))
                visemes.append({
                    "start_ms": round(time_ms, 1),
                    "duration_ms": round(consonant_length * 1000, 1),
                    "vowel": None,
                    "name": viseme_name,
                    "value": 0.5,
                })
                time_ms += consonant_length * 1000

            if vowel and vowel_length > 0:
                viseme_name = VISEME_MAP.get(vowel, ("aa", None))[0]
                visemes.append({
                    "start_ms": round(time_ms, 1),
                    "duration_ms": round(vowel_length * 1000, 1),
                    "vowel": vowel,
                    "name": viseme_name,
                    "value": 0.8,
                })
                time_ms += vowel_length * 1000

        return visemes

    def _wav_to_samples(self, wav_bytes: bytes) -> list[float]:
        """Convert WAV bytes to float samples [-1.0, 1.0]."""
        if len(wav_bytes) < 44:
            return self._raw_to_samples(wav_bytes)

        # Determine format from WAV header
        num_channels = struct.unpack_from("<H", wav_bytes, 22)[0]
        sample_width = struct.unpack_from("<H", wav_bytes, 34)[0] // 8
        data_start = struct.unpack_from("<I", wav_bytes, 40)[0] + 8
        if data_start < 44:
            data_start = 44

        audio_data = wav_bytes[data_start:]
        samples = []

        if sample_width == 2:
            fmt = "<" + ("h" * (len(audio_data) // 2))
            int_samples = struct.unpack(fmt, audio_data[:len(audio_data) - len(audio_data) % 2])
            samples = [s / 32768.0 for s in int_samples[::num_channels]]
        elif sample_width == 1:
            samples = [(b - 128) / 128.0 for i, b in enumerate(audio_data) if i % num_channels == 0]

        return samples

    def _raw_to_samples(self, raw_bytes: bytes) -> list[float]:
        """Convert raw PCM16 bytes to float samples."""
        count = len(raw_bytes) // 2
        if count == 0:
            return [0.0]
        fmt = "<" + ("h" * count)
        samples = struct.unpack(fmt, raw_bytes[:count * 2])
        return [s / 32768.0 for s in samples]

    def _frame_energy(self, frame: list[float]) -> float:
        """Compute RMS energy of a signal frame."""
        if not frame:
            return 0.0
        return sum(s * s for s in frame)
