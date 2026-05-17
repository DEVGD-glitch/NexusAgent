// ═══════════════════════════════════════════════════════════════
// NEXUS — Agent Slice
// ═══════════════════════════════════════════════════════════════

import type { StateCreator } from 'zustand';
import type { AgentMode, AgentStatus, AgentActivity, BuildStep, AgentInstance } from '@/types/nexus';
import { uid } from './utils';

export interface AgentSlice {
  provider: string;
  model: string;
  agentMode: AgentMode;
  agentStatus: AgentStatus;
  agentActivity: AgentActivity[];
  buildSteps: BuildStep[];
  agents: AgentInstance[];

  setProvider: (p: string) => void;
  setModel: (m: string) => void;
  setAgentMode: (m: AgentMode) => void;
  setAgentStatus: (s: AgentStatus) => void;
  addActivity: (a: Omit<AgentActivity, 'id' | 'timestamp'>) => void;
  clearActivity: () => void;
  addBuildStep: (s: Omit<BuildStep, 'id' | 'timestamp'>) => void;
  updateBuildStep: (id: string, status: BuildStep['status'], progress?: number) => void;
  clearBuildSteps: () => void;
  addAgent: (a: AgentInstance) => void;
  updateAgentStatus: (id: string, status: AgentInstance['status'], progress?: number) => void;
}

export const createAgentSlice: StateCreator<AgentSlice, [], [], AgentSlice> = (set) => ({
  provider: 'gemini',
  model: 'gemma-4-31b-it',
  agentMode: 'plan',
  agentStatus: 'idle',
  agentActivity: [],
  buildSteps: [],
  agents: [],

  setProvider: (p) => set({ provider: p }),
  setModel: (m) => set({ model: m }),
  setAgentMode: (m) => set({ agentMode: m }),
  setAgentStatus: (s) => set({ agentStatus: s }),

  addActivity: (a) =>
    set((s) => ({
      agentActivity: [...s.agentActivity.slice(-100), { ...a, id: uid(), timestamp: Date.now() }],
    })),
  clearActivity: () => set({ agentActivity: [] }),

  addBuildStep: (step) =>
    set((s) => ({
      buildSteps: [...s.buildSteps, { ...step, id: uid(), timestamp: Date.now() }],
    })),
  updateBuildStep: (id, status, progress) =>
    set((s) => ({
      buildSteps: s.buildSteps.map((step) =>
        step.id === id ? { ...step, status, ...(progress !== undefined ? { progress } : {}) } : step
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
});
