// ═══════════════════════════════════════════════════════════════
// NEXUS Web — API Client
// ═══════════════════════════════════════════════════════════════

import type {
  ChatMessage,
  MemoryEntry,
  KnowledgeEntity,
  CodeResult,
  SystemStatus,
} from "@/types/nexus";

const NEXUS_BACKEND = process.env.NEXT_PUBLIC_NEXUS_BACKEND || "http://127.0.0.1:8081";
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
  knowledgeQuery: (entityName: string, depth = 1) =>
    get<{ entity: KnowledgeEntity | null; relationships: unknown[]; neighbors: unknown[] }>("/knowledge/query", { entity_name: entityName, depth }),

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

  // ── File Tools ────────────────────────────────────────────
  readFile: (path: string) =>
    get<{ content: string; size_bytes: number }>("/tools/read_file", { path }),

  listFiles: (directory = ".", pattern = "*") =>
    get<{ directory: string; files: { name: string; path: string; is_dir: boolean; size: number }[] }>("/tools/list_files", { directory, pattern }),

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
};

export { NEXUS_BACKEND };
