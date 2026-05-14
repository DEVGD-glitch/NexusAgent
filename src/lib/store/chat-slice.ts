// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { Conversation, ChatMessage } from '@/types/nexus';
import { uid } from './utils';

// ── Slice Interface ──────────────────────────────────────────
export interface ChatSlice {
  conversations: Conversation[];
  activeConversationId: string | null;
  addConversation: () => string;
  setActiveConversation: (id: string) => void;
  addMessage: (convId: string, msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
}

// ── Slice Creator ────────────────────────────────────────────
export const createChatSlice: StateCreator<ChatSlice, [], [], ChatSlice> = (set) => ({
  conversations: [],
  activeConversationId: null,

  addConversation: () => {
    const id = uid();
    set((s) => ({
      conversations: [
        ...s.conversations,
        {
          id,
          title: 'Nouvelle conversation',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      ],
      activeConversationId: id,
    }));
    return id;
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  addMessage: (convId, msg) =>
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === convId
          ? {
              ...c,
              messages: [...c.messages, { ...msg, id: uid(), timestamp: Date.now() }],
              updatedAt: Date.now(),
            }
          : c
      ),
    })),
});
