// ═══════════════════════════════════════════════════════════════
// NEXUS — UI Slice (Navigation, Context, Viz, Artifacts, HITL)
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type {
  ViewId, ContextTab, VizEvent, FileTreeNode,
  Artifact, ApprovalRequest, AgentSession,
  CrystallizedSkill, AgentCapabilities,
} from '@/types/nexus';

export interface UiSlice {
  activeView: ViewId;
  contextOpen: boolean;
  contextTab: ContextTab;
  settingsOpen: boolean;
  commandOpen: boolean;
  backendConnected: boolean;

  vizEvents: VizEvent[];
  activeBuildId: string | null;
  fileTree: FileTreeNode[];

  artifacts: Artifact[];
  activeArtifactId: string | null;

  crystallizedSkills: CrystallizedSkill[];
  capabilities: AgentCapabilities | null;

  agentSessions: AgentSession[];
  pendingApprovals: ApprovalRequest[];

  setActiveView: (v: ViewId) => void;
  toggleContext: () => void;
  setContextTab: (t: ContextTab) => void;
  openContext: (t?: ContextTab) => void;
  closeContext: () => void;
  setSettingsOpen: (o: boolean) => void;
  setCommandOpen: (o: boolean) => void;
  setBackendConnected: (c: boolean) => void;

  addVizEvent: (e: VizEvent) => void;
  clearVizEvents: () => void;
  setActiveBuildId: (id: string | null) => void;
  setFileTree: (tree: FileTreeNode[]) => void;

  addArtifact: (a: Artifact) => void;
  setActiveArtifact: (id: string | null) => void;

  setCrystallizedSkills: (s: CrystallizedSkill[]) => void;
  setCapabilities: (c: AgentCapabilities | null) => void;

  setAgentSessions: (s: AgentSession[]) => void;
  updateAgentSession: (id: string, update: Partial<AgentSession>) => void;

  addApprovalRequest: (r: ApprovalRequest) => void;
  removeApprovalRequest: (id: string) => void;
}

export const createUiSlice: StateCreator<UiSlice, [], [], UiSlice> = (set) => ({
  activeView: 'chat',
  contextOpen: false,
  contextTab: 'activity',
  settingsOpen: false,
  commandOpen: false,
  backendConnected: false,

  vizEvents: [],
  activeBuildId: null,
  fileTree: [],

  artifacts: [],
  activeArtifactId: null,

  crystallizedSkills: [],
  capabilities: null,

  agentSessions: [],
  pendingApprovals: [],

  setActiveView: (v) => set({ activeView: v }),
  toggleContext: () => set((s) => ({ contextOpen: !s.contextOpen })),
  setContextTab: (t) => set({ contextTab: t, contextOpen: true }),
  openContext: (t) => set({ contextOpen: true, ...(t ? { contextTab: t } : {}) }),
  closeContext: () => set({ contextOpen: false }),
  setSettingsOpen: (o) => set({ settingsOpen: o }),
  setCommandOpen: (o) => set({ commandOpen: o }),
  setBackendConnected: (c) => set({ backendConnected: c }),

  addVizEvent: (e) => set((s) => ({ vizEvents: [...s.vizEvents, e] })),
  clearVizEvents: () => set({ vizEvents: [] }),
  setActiveBuildId: (id) => set({ activeBuildId: id }),
  setFileTree: (tree) => set({ fileTree: tree }),

  addArtifact: (a) => set((s) => ({ artifacts: [...s.artifacts, a] })),
  setActiveArtifact: (id) => set({ activeArtifactId: id }),

  setCrystallizedSkills: (s) => set({ crystallizedSkills: s }),
  setCapabilities: (c) => set({ capabilities: c }),

  setAgentSessions: (s) => set({ agentSessions: s }),
  updateAgentSession: (id, update) =>
    set((s) => ({
      agentSessions: s.agentSessions.map((a) =>
        a.id === id ? { ...a, ...update } : a
      ),
    })),

  addApprovalRequest: (r) => set((s) => ({ pendingApprovals: [...s.pendingApprovals, r] })),
  removeApprovalRequest: (id) =>
    set((s) => ({ pendingApprovals: s.pendingApprovals.filter((r) => r.id !== id) })),
});
