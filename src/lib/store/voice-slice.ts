// ═══════════════════════════════════════════════════════════════
// NEXUS — Voice Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { VoiceState, VoiceConfig, Viseme } from '@/types/nexus';

export interface VoiceSlice {
  voiceState: VoiceState;
  voiceConfig: VoiceConfig;
  currentTranscription: string;
  currentVisemes: Viseme[];

  setVoiceState: (s: VoiceState) => void;
  setVoiceConfig: (c: VoiceConfig) => void;
  setCurrentTranscription: (t: string) => void;
  setCurrentVisemes: (v: Viseme[]) => void;
}

export const createVoiceSlice: StateCreator<VoiceSlice, [], [], VoiceSlice> = (set) => ({
  voiceState: 'idle',
  voiceConfig: { engine: 'edge', voice: 'fr-FR-DeniseNeural', language: 'fr' },
  currentTranscription: '',
  currentVisemes: [],

  setVoiceState: (s) => set({ voiceState: s }),
  setVoiceConfig: (c) => set({ voiceConfig: c }),
  setCurrentTranscription: (t) => set({ currentTranscription: t }),
  setCurrentVisemes: (v) => set({ currentVisemes: v }),
});
