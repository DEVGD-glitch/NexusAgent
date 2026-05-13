// ═══════════════════════════════════════════════════════════════
// NEXUS — Global Store (Zustand) — Chat-Centric Architecture
// ═══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type {
  ViewId, AgentMode, AgentStatus, AvatarExpression,
  ChatMessage, AgentActivity, BuildStep, AgentInstance,
  Conversation, ContextTab,
} from "@/types/nexus";

function uid(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

interface NexusState {
  // ── Navigation (simplified) ───────────────────────────────
  activeView: ViewId;
  contextOpen: boolean;
  contextTab: ContextTab;
  settingsOpen: boolean;
  commandOpen: boolean;

  // ── Conversations ─────────────────────────────────────────
  conversations: Conversation[];
  activeConversationId: string | null;

  // ── LLM (default: free ZhipuAI) ──────────────────────────
  provider: string;
  model: string;

  // ── Agent State ───────────────────────────────────────────
  agentMode: AgentMode;
  agentStatus: AgentStatus;
  agentActivity: AgentActivity[];
  buildSteps: BuildStep[];
  agents: AgentInstance[];

  // ── Avatar ────────────────────────────────────────────────
  avatarEnabled: boolean;
  avatarExpression: AvatarExpression;

  // ── Connection ────────────────────────────────────────────
  backendConnected: boolean;

  // ── Actions ───────────────────────────────────────────────
  setActiveView: (v: ViewId) => void;
  toggleContext: () => void;
  setContextTab: (t: ContextTab) => void;
  openContext: (t?: ContextTab) => void;
  closeContext: () => void;
  setSettingsOpen: (o: boolean) => void;
  setCommandOpen: (o: boolean) => void;

  addConversation: () => string;
  setActiveConversation: (id: string) => void;
  addMessage: (convId: string, msg: Omit<ChatMessage, "id" | "timestamp">) => void;

  setProvider: (p: string) => void;
  setModel: (m: string) => void;

  setAgentMode: (m: AgentMode) => void;
  setAgentStatus: (s: AgentStatus) => void;
  addActivity: (a: Omit<AgentActivity, "id" | "timestamp">) => void;
  clearActivity: () => void;
  addBuildStep: (s: Omit<BuildStep, "id" | "timestamp">) => void;
  updateBuildStep: (id: string, status: BuildStep["status"], progress?: number) => void;
  clearBuildSteps: () => void;

  addAgent: (a: AgentInstance) => void;
  updateAgentStatus: (id: string, status: AgentInstance["status"], progress?: number) => void;

  toggleAvatar: () => void;
  setAvatarExpression: (e: AvatarExpression) => void;
  setBackendConnected: (c: boolean) => void;
}

export const useNexusStore = create<NexusState>((set) => ({
  // ── Initial State ─────────────────────────────────────────
  activeView: "chat",
  contextOpen: false,
  contextTab: "activity",
  settingsOpen: false,
  commandOpen: false,
  conversations: [],
  activeConversationId: null,
  provider: "zhipuai",
  model: "glm-4-flash",
  agentMode: "plan",
  agentStatus: "idle",
  agentActivity: [],
  buildSteps: [],
  agents: [],
  avatarEnabled: true,
  avatarExpression: "neutral",
  backendConnected: false,

  // ── Actions ───────────────────────────────────────────────
  setActiveView: (v) => set({ activeView: v }),
  toggleContext: () => set((s) => ({ contextOpen: !s.contextOpen })),
  setContextTab: (t) => set({ contextTab: t, contextOpen: true }),
  openContext: (t) => set({ contextOpen: true, ...(t ? { contextTab: t } : {}) }),
  closeContext: () => set({ contextOpen: false }),
  setSettingsOpen: (o) => set({ settingsOpen: o }),
  setCommandOpen: (o) => set({ commandOpen: o }),

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

  toggleAvatar: () => set((s) => ({ avatarEnabled: !s.avatarEnabled })),
  setAvatarExpression: (e) => set({ avatarExpression: e }),
  setBackendConnected: (c) => set({ backendConnected: c }),
}));
