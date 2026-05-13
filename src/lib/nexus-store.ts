// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Global Store (Zustand)
// ═══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { PanelId, AgentMode, AvatarExpression, ChatMessage, AgentActivity, BuildStep, AgentInstance, Conversation } from "@/types/nexus";

function uid(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

interface NexusState {
  // ── Navigation ────────────────────────────────────────────
  activePanel: PanelId;
  sidebarCollapsed: boolean;

  // ── Conversations ─────────────────────────────────────────
  conversations: Conversation[];
  activeConversationId: string | null;

  // ── LLM ───────────────────────────────────────────────────
  provider: string;
  model: string;

  // ── Agent State ───────────────────────────────────────────
  agentMode: AgentMode;
  agentStatus: "idle" | "thinking" | "working";
  agentActivity: AgentActivity[];
  buildSteps: BuildStep[];
  agents: AgentInstance[];
  activeAgentId: string | null;

  // ── Avatar ────────────────────────────────────────────────
  avatarEnabled: boolean;
  avatarExpression: AvatarExpression;

  // ── UI ────────────────────────────────────────────────────
  darkMode: boolean;
  backendConnected: boolean;

  // ── Actions ───────────────────────────────────────────────
  setActivePanel: (p: PanelId) => void;
  toggleSidebar: () => void;

  addConversation: () => string;
  setActiveConversation: (id: string) => void;
  addMessage: (convId: string, msg: Omit<ChatMessage, "id" | "timestamp">) => void;

  setProvider: (p: string) => void;
  setModel: (m: string) => void;

  setAgentMode: (m: AgentMode) => void;
  setAgentStatus: (s: "idle" | "thinking" | "working") => void;
  addActivity: (a: Omit<AgentActivity, "id" | "timestamp">) => void;
  clearActivity: () => void;
  addBuildStep: (s: Omit<BuildStep, "id" | "timestamp">) => void;
  updateBuildStep: (id: string, status: BuildStep["status"], progress?: number) => void;
  clearBuildSteps: () => void;

  addAgent: (a: AgentInstance) => void;
  updateAgentStatus: (id: string, status: AgentInstance["status"], progress?: number) => void;
  setActiveAgent: (id: string | null) => void;

  toggleAvatar: () => void;
  setAvatarExpression: (e: AvatarExpression) => void;

  setDarkMode: (d: boolean) => void;
  setBackendConnected: (c: boolean) => void;
}

export const useNexusStore = create<NexusState>((set) => ({
  // ── Initial State ─────────────────────────────────────────
  activePanel: "chat",
  sidebarCollapsed: false,
  conversations: [],
  activeConversationId: null,
  provider: "gemini",
  model: "gemini-2.5-flash",
  agentMode: "plan",
  agentStatus: "idle",
  agentActivity: [],
  buildSteps: [],
  agents: [],
  activeAgentId: null,
  avatarEnabled: true,
  avatarExpression: "neutral",
  darkMode: true,
  backendConnected: false,

  // ── Actions ───────────────────────────────────────────────
  setActivePanel: (p) => set({ activePanel: p }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  addConversation: () => {
    const id = uid();
    set((s) => ({
      conversations: [...s.conversations, { id, title: "Nouvelle conversation", messages: [], createdAt: Date.now(), updatedAt: Date.now() }],
      activeConversationId: id,
    }));
    return id;
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  addMessage: (convId, msg) =>
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === convId ? { ...c, messages: [...c.messages, { ...msg, id: uid(), timestamp: Date.now() }], updatedAt: Date.now() } : c
      ),
    })),

  setProvider: (p) => set({ provider: p }),
  setModel: (m) => set({ model: m }),

  setAgentMode: (m) => set({ agentMode: m }),
  setAgentStatus: (s) => set({ agentStatus: s }),

  addActivity: (a) =>
    set((s) => ({
      agentActivity: [...s.agentActivity.slice(-100), { ...a, id: uid(), timestamp: Date.now() }],
    })),

  clearActivity: () => set({ agentActivity: [] }),

  addBuildStep: (s) =>
    set((state) => ({
      buildSteps: [...state.buildSteps, { ...s, id: uid(), timestamp: Date.now() }],
    })),

  updateBuildStep: (id, status, progress) =>
    set((state) => ({
      buildSteps: state.buildSteps.map((s) =>
        s.id === id ? { ...s, status, ...(progress !== undefined ? { progress } : {}) } : s
      ),
    })),

  clearBuildSteps: () => set({ buildSteps: [] }),

  addAgent: (a) => set((s) => ({ agents: [...s.agents, a] })),
  updateAgentStatus: (id, status, progress) =>
    set((s) => ({
      agents: s.agents.map((a) =>
        a.id === id ? { ...a, status, ...(progress !== undefined ? { progress } : {}) } : a
      ),
    })),
  setActiveAgent: (id) => set({ activeAgentId: id }),

  toggleAvatar: () => set((s) => ({ avatarEnabled: !s.avatarEnabled })),
  setAvatarExpression: (e) => set({ avatarExpression: e }),

  setDarkMode: (d) => set({ darkMode: d }),
  setBackendConnected: (c) => set({ backendConnected: c }),
}));
