// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { Conversation, ChatMessage } from '@/types/nexus';
import { uid } from './utils';
import { saveConversation, getAllConversations, deleteConversation as deleteConvDB, saveMessage, getMessages } from '../db';

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
    const id = crypto.randomUUID();
    const conv: Conversation = {
      id,
      title: 'Nouvelle conversation',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    set((s) => ({
      conversations: [conv, ...s.conversations],
      activeConversationId: id,
    }));
    saveConversation(conv).catch(() => {});
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

  addMessage: (convId, msg) => {
    const msgWithId = { ...msg, id: msg.id || crypto.randomUUID() };
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === convId
          ? { ...c, messages: [...c.messages, msgWithId], updatedAt: Date.now() }
          : c
      ),
    }));
    saveMessage({ ...msgWithId, conversationId: convId }).catch(() => {});
    saveConversation({ id: convId, updatedAt: Date.now() } as Conversation).catch(() => {});
  },
});
