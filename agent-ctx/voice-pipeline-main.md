# Task: Voice Pipeline for NexusAgent Backend

## Summary

Built a complete voice pipeline for the NexusAgent backend at `/home/z/my-project/NexusAgent/nexus/comms/` and related API routes.

## Files Created

### 1. `nexus/comms/voice_pipeline.py` (NEW — ~580 lines)
Complete voice pipeline implementation with 6 classes:

- **SileroVAD** — Voice Activity Detection using silero-vad model with energy-based fallback
- **WhisperSTT** — Speech-to-Text with 3-tier fallback: OpenAI API → faster-whisper → basic
- **EdgeTTS** — Free Text-to-Speech using edge-tts package (100% free, no API key)
- **VoiceVOXBridge** — Anime TTS via VoiceVOX server with EdgeTTS fallback
- **LipSyncExtractor** — Audio → Viseme extraction with VRM blend shape mapping (A, I, U, E, O)
- **VoicePipeline** — Orchestrator: `process_audio_input()` (VAD+STT), `process_text_output()` (TTS+LipSync)

All dependencies handled with try/except for graceful degradation. Heavy models lazy-loaded.

### 2. `nexus/api/voice_routes.py` (NEW — ~300 lines)
FastAPI router with voice API endpoints:

- `POST /voice/transcribe` — Upload base64 audio → get transcription
- `POST /voice/synthesize` — Text → audio bytes + viseme data (supports edge and voicevox engines)
- `GET /voice/voices` — List available TTS voices
- `WebSocket /voice/stream` — Real-time bidirectional voice streaming

All routes use lazy-loaded VoicePipeline singleton.

## Files Modified

### 3. `nexus/comms/avatar/avatar_manager.py` (ENHANCED)
Added:
- WebSocket client management (`register_ws_client`, `unregister_ws_client`, `handle_ws_message`)
- Lip-sync viseme data broadcast to connected WS clients during speech
- `AvatarState` dataclass tracking: status, expression, speaking, thinking, speaker, VRM path
- `AvatarStatus` enum: IDLE, SPEAKING, THINKING, LISTENING, ERROR
- Event emission: `avatar_expression_change`, `avatar_speaking_start`, `avatar_speaking_end`
- Event listener system: `on()` / `off()` for callback registration
- WebSocket commands: set_expression, set_vrm, set_speaker, speak, stop_speaking, get_state
- Integration with NEXUS EventBroadcaster for cross-system events

### 4. `nexus/api/gateway.py` (MODIFIED)
Added voice router inclusion after app creation:
```python
from nexus.api.voice_routes import router as voice_router
app.include_router(voice_router)
```
Wrapped in try/except for graceful degradation.

### 5. `nexus/core/events.py` (MODIFIED)
Added new event types to `VALID_EVENT_TYPES`:
- `avatar_expression_change`
- `avatar_speaking_start`
- `avatar_speaking_end`

### 6. `nexus/comms/__init__.py` (UPDATED)
Added exports for all voice_pipeline classes:
VoicePipeline, SileroVAD, WhisperSTT, EdgeTTS, VoiceVOXBridge, LipSyncExtractor, etc.

### 7. `nexus/comms/avatar/__init__.py` (UPDATED)
Added exports for new avatar_manager types:
AvatarState, AvatarStatus (in addition to existing exports)

### 8. `nexus/api/__init__.py` (UPDATED)
Added documentation for voice_routes import.

## Testing
- All files pass Python AST syntax check
- All imports work correctly
- Functional tests pass for: SileroVAD, EdgeTTS, LipSyncExtractor, VoicePipeline, AvatarManager
- Voice engine switching works (edge ↔ voicevox)
- Silence audio correctly produces 0 visemes
- AvatarManager state tracking operational
