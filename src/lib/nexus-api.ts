// ═══════════════════════════════════════════════════════════════
// NEXUS — API Client (Chat-Centric)
// ═══════════════════════════════════════════════════════════════

import type {
  ChatMessage, MemoryEntry, KnowledgeEntity,
  CodeResult, SystemStatus,
  MemoryRecallResult, CrystallizedSkill, AgentCapabilities,
  VizEvent, Viseme,
} from "@/types/nexus";

const API_BASE = "/api/nexus";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const searchParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) searchParams.set(k, String(v));
    });
  }
  const qs = searchParams.toString();
  const res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const nexusApi = {
  // ── Chat ──────────────────────────────────────────────────
  chat: (messages: Pick<ChatMessage, "role" | "content">[], provider?: string, model?: string) =>
    post<{ content: string; provider: string; model: string; usage: { prompt_tokens: number; completion_tokens: number } }>("/chat", { messages, provider, model }),

  chatStream: (messages: Pick<ChatMessage, "role" | "content">[], provider?: string, model?: string) =>
    fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, provider, model }),
    }),

  // ── Tasks ─────────────────────────────────────────────────
  runTask: (task: string, provider?: string) =>
    post<{ result: string; status: string; plan: string; steps: number; latency_ms: number }>("/run", { task, provider }),

  // ── Memory ────────────────────────────────────────────────
  searchMemory: (query: string, namespace = "knowledge", top_k = 5) =>
    get<MemoryEntry[]>("/tools/search_memory", { query, namespace, top_k }),

  storeMemory: (text: string, namespace = "knowledge", source = "user") =>
    post<{ doc_id: string; namespace: string; status: string }>("/tools/store_memory", { text, namespace, source }),

  memoryStats: () =>
    get<{ namespaces: Record<string, { count: number }> }>("/memory/stats"),

  // ── Knowledge ─────────────────────────────────────────────
  knowledgeSearch: (query: string, entityType?: string, limit = 20) =>
    get<KnowledgeEntity[]>("/knowledge/search", { query, entity_type: entityType, limit }),

  // ── Agents ────────────────────────────────────────────────
  spawnAgent: (task: string, agentType = "general") =>
    post<{ status: string; instance_id: string; agent_type: string }>("/agents/spawn", { task, agent_type: agentType }),

  listAgents: () =>
    get<{ types: string[]; stats: Record<string, number> }>("/agents/list"),

  // ── Code ──────────────────────────────────────────────────
  executeCode: (code: string, language = "python", timeout = 30, sandboxed = true) =>
    post<CodeResult>("/code/execute", { code, language, timeout, sandboxed }),

  // ── Web Search ────────────────────────────────────────────
  webSearch: (query: string, numResults = 5) =>
    get<{ query: string; results: { title: string; url: string; snippet: string }[] }>("/tools/web_search", { query, num_results: numResults }),

  // ── System ────────────────────────────────────────────────
  systemStatus: () => get<SystemStatus>("/status"),
  providers: () => get<Record<string, { available: boolean; default_model: string; last_error?: string }>>("/providers"),
  health: () => get<{ status: string }>("/health"),

  // ── Security ──────────────────────────────────────────────
  auditLog: (limit = 50) =>
    get<{ entries: unknown[]; count: number }>("/security/audit", { limit }),

  // ── Generic Tool ──────────────────────────────────────────
  genericTool: (toolName: string, params: Record<string, unknown> = {}) =>
    post<unknown>(`/tools/${toolName}`, params),

  // ── Memory (5-layer) ──
  memoryRecall: (query: string, layers?: string[]) =>
    post<{ results: MemoryRecallResult[] }>('/memory/recall', { query, layers }),

  memoryStore: (content: string, type: string = "auto") =>
    post<{ status: string }>('/memory/store', { content, type }),

  episodicRecord: (event: string, context?: string) =>
    post<{ status: string }>('/memory/episodic/record', { event, context }),

  episodicRecall: (query: string, topK: number = 5) =>
    post<{ results: unknown[] }>('/memory/episodic/recall', { query, top_k: topK }),

  semanticAddFact: (fact: string, category?: string) =>
    post<{ status: string }>('/memory/semantic/add_fact', { fact, category }),

  semanticQuery: (query: string) =>
    post<{ results: unknown[] }>('/memory/semantic/query', { query }),

  proceduralCrystallize: (skillName: string, pattern: string) =>
    post<{ skill_id: string }>('/memory/procedural/crystallize', { skill_name: skillName, pattern }),

  proceduralFindRelevant: (task: string) =>
    post<{ skills: CrystallizedSkill[] }>('/memory/procedural/find_relevant', { task }),

  identityUpdate: (updates: Record<string, unknown>) =>
    post<{ status: string }>('/memory/identity/update', { updates }),

  identityProfile: () =>
    get<Record<string, unknown>>('/memory/identity/profile'),

  memoryCompact: () =>
    post<{ status: string }>('/memory/compact'),

  // ── Skills & Capabilities ──
  capabilities: () =>
    get<AgentCapabilities>('/capabilities'),

  listSkills: () =>
    get<CrystallizedSkill[]>('/skills'),

  crystallizeSkill: (name: string, pattern: string) =>
    post<{ skill_id: string }>('/skills/crystallize', { name, pattern }),

  executeSkill: (name: string, args: Record<string, unknown> = {}) =>
    post<unknown>('/skills/execute', { name, args }),

  // ── Voice ──
  voiceTranscribe: (audioBase64: string, language: string = "fr") =>
    post<{ text: string }>('/voice/transcribe', { audio: audioBase64, language }),

  voiceSynthesize: (text: string, engine: string = "edge", voice?: string) =>
    post<{ audio: string; visemes: Viseme[] }>('/voice/synthesize', { text, engine, voice }),

  voiceVoices: () =>
    get<{ voices: { id: string; name: string; language: string }[] }>('/voice/voices'),

  // ── Crons ──
  scheduleCron: (task: string, schedule: string, cronId?: string) =>
    post<{ cron_id: string }>('/crons/schedule', { task, schedule, cron_id: cronId }),

  listCrons: () =>
    get<{ crons: { id: string; task: string; schedule: string; next_run: string }[] }>('/crons/list'),

  deleteCron: (cronId: string) =>
    fetch(`${API_BASE}/crons/${cronId}`, { method: 'DELETE' }).then(r => r.json()),

  // ── Visualization ──
  vizHistory: (buildId: string) =>
    get<{ events: VizEvent[] }>(`/viz/history/${buildId}`),

  vizActive: () =>
    get<{ builds: { id: string; event_count: number; latest_status: string }[] }>('/viz/active'),

  // ── HITL Approvals ──
  approveAction: (requestId: string) =>
    post<{ status: string }>('/agents/approval', { request_id: requestId, behavior: 'allow' }),

  denyAction: (requestId: string) =>
    post<{ status: string }>('/agents/approval', { request_id: requestId, behavior: 'deny' }),
};
