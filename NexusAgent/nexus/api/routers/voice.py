"""NEXUS API — Voice endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/engines")
async def list_voice_engines():
    """List available TTS engines."""
    return {"engines": ["edge", "voicevox"]}


@router.get("/voices")
async def list_voices():
    """List available voices."""
    return {
        "edge": [
            "fr-FR-DeniseNeural", "fr-FR-HenriNeural",
            "en-US-AriaNeural", "en-US-GuyNeural",
        ],
        "voicevox": ["四国めたん", "ずんだもん"],
    }
