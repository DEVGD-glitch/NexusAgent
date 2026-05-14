// ═══════════════════════════════════════════════════════════════
// NEXUS — Combined Store (Zustand Slices)
// ═══════════════════════════════════════════════════════════════
// Combines all domain slices into a single store.
// Backwards-compatible: useNexusStore works exactly as before.

import { create } from 'zustand';
import type { ChatSlice } from './chat-slice';
import { createChatSlice } from './chat-slice';
import type { AgentSlice } from './agent-slice';
import { createAgentSlice } from './agent-slice';
import type { AvatarSlice } from './avatar-slice';
import { createAvatarSlice } from './avatar-slice';
import type { VoiceSlice } from './voice-slice';
import { createVoiceSlice } from './voice-slice';
import type { UiSlice } from './ui-slice';
import { createUiSlice } from './ui-slice';

export type NexusState = ChatSlice & AgentSlice & AvatarSlice & VoiceSlice & UiSlice;

export const useNexusStore = create<NexusState>()((...a) => ({
  ...createChatSlice(...a),
  ...createAgentSlice(...a),
  ...createAvatarSlice(...a),
  ...createVoiceSlice(...a),
  ...createUiSlice(...a),
}));
