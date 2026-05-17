// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { Conversation, ChatMessage } from '@/types/nexus';
import { uid } from './utils';

// ── Constants ────────────────────────────────────────────────
const MAX_MESSAGES_PER_CONVERSATION = 500;

// ── Slice Interface ──────────────────────────────────────────
export interface ChatSlice {
  conversations: Conversation[];
  activeConversationId: string | null;
  addConversation: () => string;
  setActiveConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
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

  deleteConversation: (id) =>
    set((s) => {
      const remaining = s.conversations.filter((c) => c.id !== id);
      const needsNewActive = s.activeConversationId === id;
      return {
        conversations: remaining,
        activeConversationId: needsNewActive
          ? remaining.length > 0
            ? remaining[remaining.length - 1].id
            : null
          : s.activeConversationId,
      };
    }),

  addMessage: (convId, msg) =>
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === convId
          ? {
              ...c,
              messages: [
                ...c.messages.slice(-(MAX_MESSAGES_PER_CONVERSATION - 1)),
                { ...msg, id: uid(), timestamp: Date.now() },
              ],
              updatedAt: Date.now(),
            }
          : c
      ),
    })),
});
