// ═══════════════════════════════════════════════════════════════
// NEXUS — Avatar Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { AvatarExpression } from '@/types/nexus';

export interface AvatarSlice {
  avatarEnabled: boolean;
  avatarExpression: AvatarExpression;
  avatarModelUrl: string | null;
  vrmHubOpen: boolean;
  avatarProfessionalMode: boolean;

  toggleAvatar: () => void;
  setAvatarExpression: (e: AvatarExpression) => void;
  setAvatarModelUrl: (url: string | null) => void;
  setVrmHubOpen: (open: boolean) => void;
  setAvatarProfessionalMode: (mode: boolean) => void;
}

export const createAvatarSlice: StateCreator<AvatarSlice, [], [], AvatarSlice> = (set) => ({
  avatarEnabled: true,
  avatarExpression: 'neutral',
  avatarModelUrl: null,
  vrmHubOpen: false,
  avatarProfessionalMode: false,

  toggleAvatar: () => set((s) => ({ avatarEnabled: !s.avatarEnabled })),
  setAvatarExpression: (e) => set({ avatarExpression: e }),
  setAvatarModelUrl: (url) => set({ avatarModelUrl: url }),
  setVrmHubOpen: (open) => set({ vrmHubOpen: open }),
  setAvatarProfessionalMode: (mode) => set({ avatarProfessionalMode: mode }),
});
