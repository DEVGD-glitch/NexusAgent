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

// Restore persisted voice config
function getPersistedVoiceConfig(): VoiceConfig {
  if (typeof window === 'undefined') return { engine: 'edge', voice: 'fr-FR-DeniseNeural', language: 'fr' };
  try {
    const saved = localStorage.getItem('nexus_voice_config');
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return { engine: 'edge', voice: 'fr-FR-DeniseNeural', language: 'fr' };
}

export const createVoiceSlice: StateCreator<VoiceSlice, [], [], VoiceSlice> = (set) => ({
  voiceState: 'idle',
  voiceConfig: getPersistedVoiceConfig(),
  currentTranscription: '',
  currentVisemes: [],

  setVoiceState: (s) => set({ voiceState: s }),
  setVoiceConfig: (c) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('nexus_voice_config', JSON.stringify(c));
    }
    set({ voiceConfig: c });
  },
  setCurrentTranscription: (t) => set({ currentTranscription: t }),
  setCurrentVisemes: (v) => set({ currentVisemes: v }),
});
