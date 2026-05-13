# Task: Voice UI + ChatView + WebSocket Hook Updates for NexusAgent V3

## Summary

Built voice interaction components, updated WebSocket hook with new event types, and enhanced ChatView with GenUI card wiring, panels, persistence, and streaming.

## Files Created

### 1. `src/components/nexus/voice-ui.tsx` (NEW — ~280 lines)
Three voice interaction components:

- **VoiceWaveform** — CSS-animated waveform visualization (5-7 bars with staggered heights/delays). Works for both recording and playback states.
- **TTSPlayback** — Text-to-speech playback component. Calls `nexusApi.voiceSynthesize()`, plays audio via `Audio` API, updates avatar visemes for lip-sync. User-triggered play/stop button with visual feedback.
- **VoiceButton** — Floating button near chat input. States: idle (mic icon), recording (pulsing red circle + waveform), transcribing (spinner), playing (speaker), error (mic-off). Uses MediaRecorder API to capture audio, sends to `nexusApi.voiceTranscribe()`, puts transcribed text into chat input.

## Files Modified

### 2. `src/hooks/use-nexus-ws.ts` (UPDATED — added 9 new event handlers)
Added handlers for new V3 WebSocket event types:

- `viz_event` — Adds to vizEvents store for LiveVizPanel
- `artifact_update` — Adds artifact to artifacts store
- `voice_audio` — Plays audio if TTS enabled via Audio API
- `avatar_visemes` — Updates current visemes for lip-sync
- `agent_spawned` — Creates new agent session entry
- `agent_completed` — Updates agent session status
- `approval_request` — Adds HITL approval request
- `stream_token` — Accumulates streaming tokens (was no-op before)
- `capabilities_update` — Updates agent capabilities

### 3. `src/components/nexus/chat-view.tsx` (UPDATED — major enhancements)
Seven changes:

1. **GenUI card wiring** — ActivityCards component renders MemoryCard (memory*), WebResultCard (web*), CodeResultCard (code*/execute*), KnowledgeCard (knowledge*) based on activity type
2. **VoiceButton** — Added next to send button in input area
3. **LiveVizPanel** — Shows to the right of chat when vizEvents.length > 0 (resizable via ResizablePanelGroup)
4. **ArtifactPanel** — Shows artifact renderer (iframe for HTML, syntax-highlighted code, image, document) when activeArtifactId is set
5. **Stop button** — Red square button appears when agentStatus !== "idle", aborts fetch request
6. **Conversation persistence** — Saves/loads conversations from localStorage on every change/mount
7. **stream_token handling** — Accumulates streaming tokens from WebSocket into streamingContent state

Additional improvements:
- TTS toggle button in input area
- HITL approval request rendering
- Viz panel toggle in status bar
- Auto-show viz panel when events arrive

## Lint Status
All lint checks pass (0 errors, 0 warnings).
