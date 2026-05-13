// ═══════════════════════════════════════════════════════════════
// NEXUS — Global Store (Zustand) — Chat-Centric Architecture
// ═══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type {
  ViewId, AgentMode, AgentStatus, AvatarExpression,
  ChatMessage, AgentActivity, BuildStep, AgentInstance,
  Conversation, ContextTab,
  VizEvent, FileTreeNode, Artifact, VoiceState, VoiceConfig, Viseme,
  CrystallizedSkill, AgentCapabilities, AgentSession, ApprovalRequest,
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

  // ── Visualization ──
  vizEvents: VizEvent[];
  activeBuildId: string | null;
  fileTree: FileTreeNode[];

  // ── Artifacts ──
  artifacts: Artifact[];
  activeArtifactId: string | null;

  // ── Voice ──
  voiceState: VoiceState;
  voiceConfig: VoiceConfig;
  currentTranscription: string;
  currentVisemes: Viseme[];

  // ── Skills ──
  crystallizedSkills: CrystallizedSkill[];
  capabilities: AgentCapabilities | null;

  // ── Multi-Agent ──
  agentSessions: AgentSession[];

  // ── HITL ──
  pendingApprovals: ApprovalRequest[];

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

  // Viz
  addVizEvent: (e: VizEvent) => void;
  clearVizEvents: () => void;
  setActiveBuildId: (id: string | null) => void;
  setFileTree: (tree: FileTreeNode[]) => void;

  // Artifacts
  addArtifact: (a: Artifact) => void;
  setActiveArtifact: (id: string | null) => void;

  // Voice
  setVoiceState: (s: VoiceState) => void;
  setVoiceConfig: (c: VoiceConfig) => void;
  setCurrentTranscription: (t: string) => void;
  setCurrentVisemes: (v: Viseme[]) => void;

  // Skills
  setCrystallizedSkills: (s: CrystallizedSkill[]) => void;
  setCapabilities: (c: AgentCapabilities | null) => void;

  // Multi-Agent
  setAgentSessions: (s: AgentSession[]) => void;
  updateAgentSession: (id: string, update: Partial<AgentSession>) => void;

  // HITL
  addApprovalRequest: (r: ApprovalRequest) => void;
  removeApprovalRequest: (id: string) => void;
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

  vizEvents: [],
  activeBuildId: null,
  fileTree: [],

  artifacts: [],
  activeArtifactId: null,

  voiceState: "idle",
  voiceConfig: { engine: "edge", voice: "fr-FR-DeniseNeural", language: "fr" },
  currentTranscription: "",
  currentVisemes: [],

  crystallizedSkills: [],
  capabilities: null,

  agentSessions: [],

  pendingApprovals: [],

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

  // Viz
  addVizEvent: (e) => set((s) => ({ vizEvents: [...s.vizEvents, e] })),
  clearVizEvents: () => set({ vizEvents: [] }),
  setActiveBuildId: (id) => set({ activeBuildId: id }),
  setFileTree: (tree) => set({ fileTree: tree }),

  // Artifacts
  addArtifact: (a) => set((s) => ({ artifacts: [...s.artifacts, a] })),
  setActiveArtifact: (id) => set({ activeArtifactId: id }),

  // Voice
  setVoiceState: (s) => set({ voiceState: s }),
  setVoiceConfig: (c) => set({ voiceConfig: c }),
  setCurrentTranscription: (t) => set({ currentTranscription: t }),
  setCurrentVisemes: (v) => set({ currentVisemes: v }),

  // Skills
  setCrystallizedSkills: (s) => set({ crystallizedSkills: s }),
  setCapabilities: (c) => set({ capabilities: c }),

  // Multi-Agent
  setAgentSessions: (s) => set({ agentSessions: s }),
  updateAgentSession: (id, update) =>
    set((s) => ({
      agentSessions: s.agentSessions.map((a) =>
        a.id === id ? { ...a, ...update } : a
      ),
    })),

  // HITL
  addApprovalRequest: (r) => set((s) => ({ pendingApprovals: [...s.pendingApprovals, r] })),
  removeApprovalRequest: (id) =>
    set((s) => ({ pendingApprovals: s.pendingApprovals.filter((r) => r.id !== id) })),
}));
