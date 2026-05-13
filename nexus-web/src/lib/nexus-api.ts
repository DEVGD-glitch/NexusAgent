export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResponse {
  content: string;
  provider: string;
  model: string;
  usage: { prompt_tokens: number; completion_tokens: number };
}

export interface MemoryEntry {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
  distance: number;
}

export interface KnowledgeEntity {
  name: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface KnowledgeRelation {
  source: string;
  target: string;
  relation: string;
}

export interface AgentInfo {
  instance_id: string;
  agent_type: string;
  task: string;
  status: string;
}

export interface SystemStatus {
  agent: string;
  version: string;
  status: string;
  environment: string;
  providers_configured: string[];
  uptime_seconds: number;
  platform: string;
  python_version: string;
}

export interface ProviderStatus {
  [provider: string]: {
    available: boolean;
    default_model: string;
    last_error?: string;
  };
}

export interface AuditEntry {
  timestamp: string;
  category: string;
  action: string;
  target: string;
  outcome: string;
}

export interface CodeResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  execution_time_ms: number;
}

const BASE = "/api/nexus";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  chat: (messages: ChatMessage[], provider?: string, model?: string) =>
    post<ChatResponse>("/chat", { messages, provider, model }),

  runTask: (task: string) =>
    post<{ result: string; status: string; plan: string }>("/run", { task }),

  searchMemory: (query: string, namespace = "knowledge", top_k = 5) =>
    get<MemoryEntry[]>("/tools/search_memory", { query, namespace, top_k }),

  storeMemory: (text: string, namespace = "knowledge", source = "user") =>
    post<{ doc_id: string; namespace: string; status: string }>("/tools/store_memory", { text, namespace, source }),

  memoryStats: () =>
    get<{ namespaces: Record<string, { count: number }> }>("/memory/stats"),

  knowledgeQuery: (entityName: string, depth = 1) =>
    get<{ entity: KnowledgeEntity | null; relationships: KnowledgeRelation[]; neighbors: unknown[] }>(
      "/knowledge/query", { entity_name: entityName, depth }
    ),

  knowledgeSearch: (query: string, entityType?: string, limit = 20) =>
    get<KnowledgeEntity[]>("/knowledge/search", { query, entity_type: entityType, limit }),

  spawnAgent: (task: string, agentType = "general") =>
    post<{ status: string; instance_id: string; agent_type: string }>("/agents/spawn", { task, agent_type: agentType }),

  listAgents: () =>
    get<{ types: string[]; stats: Record<string, number> }>("/agents/list"),

  executeCode: (code: string, language = "python", timeout = 30, sandboxed = true) =>
    post<CodeResult>("/code/execute", { code, language, timeout, sandboxed }),

  readFile: (path: string) =>
    get<{ content: string; size_bytes: number }>("/tools/read_file", { path }),

  webSearch: (query: string, numResults = 5) =>
    get<{ query: string; results: { title: string; url: string; snippet: string }[] }>(
      "/tools/web_search", { query, num_results: numResults }
    ),

  systemStatus: () => get<SystemStatus>("/status"),
  providers: () => get<ProviderStatus>("/providers"),
  health: () => get<{ status: string }>("/health"),
  getConfig: () => get<Record<string, unknown>>("/config"),

  auditLog: (limit = 50) =>
    get<{ entries: AuditEntry[]; count: number }>("/security/audit", { limit }),

  genericTool: (toolName: string, params: Record<string, unknown> = {}) =>
    post<unknown>(`/tools/${toolName}`, params),
};
