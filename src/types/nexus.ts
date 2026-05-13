// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Type Definitions
// ═══════════════════════════════════════════════════════════════

export type PanelId = "chat" | "agents" | "code" | "memory" | "knowledge" | "tools" | "security" | "settings";

export type AgentMode = "plan" | "build";

export type AgentStatus = "idle" | "thinking" | "working" | "completed" | "failed";

export type AvatarExpression = "neutral" | "joy" | "thinking" | "surprise" | "relaxed" | "sad" | "angry";

// ── Chat ──────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  provider?: string;
  model?: string;
  tokens?: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

// ── Agent Activity (real-time) ────────────────────────────────

export type ActivityType =
  | "agent_thinking"
  | "agent_action"
  | "tool_call"
  | "tool_result"
  | "file_create"
  | "file_edit"
  | "code_building"
  | "task_step"
  | "task_done"
  | "error"
  | "avatar_expression"
  | "stream_token";

export interface AgentActivity {
  id: string;
  type: ActivityType;
  content: string;
  toolName?: string;
  details?: string;
  timestamp: number;
  progress?: number;
}

// ── Brick-by-Brick Building ───────────────────────────────────

export type BuildStatus = "pending" | "building" | "completed" | "error";

export interface BuildStep {
  id: string;
  type: "file_create" | "file_edit" | "code_line" | "dependency" | "config" | "test" | "deploy";
  label: string;
  detail: string;
  status: BuildStatus;
  progress: number;
  timestamp: number;
  content?: string;
  language?: string;
}

// ── Agent Instances ───────────────────────────────────────────

export interface AgentInstance {
  id: string;
  name: string;
  type: string;
  status: "running" | "completed" | "failed" | "pending";
  task: string;
  progress: number;
  startedAt: number;
  completedAt?: number;
}

// ── LLM Providers ─────────────────────────────────────────────

export interface ProviderInfo {
  id: string;
  name: string;
  available: boolean;
  requiresKey: boolean;
  defaultModel: string;
  models: string[];
  lastError?: string;
  tier: "free" | "paid" | "local";
}

// ── Memory ────────────────────────────────────────────────────

export interface MemoryEntry {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
  distance: number;
}

export interface MemoryNamespace {
  name: string;
  count: number;
}

// ── Knowledge ─────────────────────────────────────────────────

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

// ── Code Execution ────────────────────────────────────────────

export interface CodeResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  execution_time_ms: number;
}

// ── System Status ─────────────────────────────────────────────

export interface SystemStatus {
  agent: string;
  version: string;
  status: string;
  environment: string;
  providers_configured: string[];
  uptime_seconds: number;
}

// ── WebSocket Events ──────────────────────────────────────────

export interface WSEvent {
  type: ActivityType;
  data: Record<string, unknown>;
  timestamp: number;
}
