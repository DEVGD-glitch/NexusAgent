"use client";

import { create } from "zustand";
import type { ChatMessage } from "./nexus-api";

export type PanelId = "agents" | "chat" | "tasks" | "code" | "memory" | "knowledge" | "tools" | "settings";

export type AgentMode = "plan" | "build";

export interface AgentActivity {
  id: string;
  type: "thought" | "tool_call" | "tool_result" | "task_step" | "task_done" | "error" | "file_create" | "file_edit" | "code_diff";
  content: string;
  toolName?: string;
  details?: string;
  timestamp: number;
}

export interface AgentInstance {
  id: string;
  name: string;
  type: string;
  status: "running" | "completed" | "failed" | "pending";
  task: string;
  progress: number;
  startedAt: number;
  completedAt?: number;
  activityCount: number;
}

function generateId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

interface NexusState {
  activePanel: PanelId;
  conversations: { id: string; messages: ChatMessage[] }[];
  activeConversationId: string | null;
  provider: string;
  model: string;
  darkMode: boolean;
  sidebarCollapsed: boolean;
  avatarEnabled: boolean;
  agentThinking: boolean;
  agentActivity: AgentActivity[];
  agentMode: AgentMode;
  agents: AgentInstance[];
  activeAgentId: string | null;

  setActivePanel: (panel: PanelId) => void;
  setProvider: (p: string) => void;
  setModel: (m: string) => void;
  toggleDarkMode: () => void;
  toggleSidebar: () => void;
  toggleAvatar: () => void;
  setAgentThinking: (v: boolean) => void;
  addActivity: (a: Omit<AgentActivity, "id" | "timestamp">) => void;
  clearActivity: () => void;

  addConversation: () => string;
  setActiveConversation: (id: string) => void;
  addMessage: (conversationId: string, message: ChatMessage) => void;

  setAgentMode: (mode: AgentMode) => void;
  addAgent: (agent: AgentInstance) => void;
  updateAgentStatus: (id: string, status: AgentInstance["status"], progress?: number) => void;
  removeAgent: (id: string) => void;
  setActiveAgent: (id: string | null) => void;
}

export const useNexusStore = create<NexusState>((set) => ({
  activePanel: "agents",
  conversations: [],
  activeConversationId: null,
  provider: "gemini",
  model: "gemma-4-31b-it",
  darkMode: true,
  sidebarCollapsed: false,
  avatarEnabled: false,
  agentThinking: false,
  agentActivity: [],
  agentMode: "plan",
  agents: [],
  activeAgentId: null,

  setActivePanel: (panel) => set({ activePanel: panel }),
  setProvider: (p) => set({ provider: p }),
  setModel: (m) => set({ model: m }),
  toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleAvatar: () => set((s) => ({ avatarEnabled: !s.avatarEnabled })),
  setAgentThinking: (v) => set({ agentThinking: v }),
  addActivity: (a) => set((s) => ({
    agentActivity: [...s.agentActivity.slice(-50), { ...a, id: generateId(), timestamp: Date.now() }]
  })),
  clearActivity: () => set({ agentActivity: [] }),

  addConversation: () => {
    const id = generateId();
    set((s) => ({
      conversations: [...s.conversations, { id, messages: [] }],
      activeConversationId: id,
    }));
    return id;
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  addMessage: (conversationId, message) =>
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === conversationId ? { ...c, messages: [...c.messages, message] } : c
      ),
    })),

  setAgentMode: (mode) => set({ agentMode: mode }),

  addAgent: (agent) => set((s) => ({
    agents: [...s.agents, agent]
  })),

  updateAgentStatus: (id, status, progress) => set((s) => ({
    agents: s.agents.map((a) =>
      a.id === id
        ? { ...a, status, ...(progress !== undefined ? { progress } : {}), ...(status === "completed" || status === "failed" ? { completedAt: Date.now() } : {}) }
        : a
    )
  })),

  removeAgent: (id) => set((s) => ({
    agents: s.agents.filter((a) => a.id !== id)
  })),

  setActiveAgent: (id) => set({ activeAgentId: id }),
}));
