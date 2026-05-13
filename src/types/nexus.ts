// ═══════════════════════════════════════════════════════════════
// NEXUS — Type Definitions (Chat-Centric Architecture)
// ═══════════════════════════════════════════════════════════════

// ── Views ──────────────────────────────────────────────────────
export type ViewId = "chat" | "code";

// ── Chat ───────────────────────────────────────────────────────
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  /** Embedded tool calls / agent activities inside the message */
  activities?: AgentActivity[];
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

// ── Agent Activity (inline in chat, not separate panel) ────────
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

// ── Build Steps (shown contextually in chat) ───────────────────
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

// ── Agent Mode ─────────────────────────────────────────────────
export type AgentMode = "plan" | "build";
export type AgentStatus = "idle" | "thinking" | "working";

// ── Avatar ─────────────────────────────────────────────────────
export type AvatarExpression = "neutral" | "joy" | "thinking" | "surprise" | "relaxed" | "sad" | "angry";

// ── Context Panel (right sidebar) ──────────────────────────────
export type ContextTab = "activity" | "memory" | "knowledge" | "agents";

// ── LLM Providers ──────────────────────────────────────────────
export interface ProviderInfo {
  id: string;
  name: string;
  tier: "free" | "paid" | "local";
  models: string[];
  requiresKey: boolean;
}

// ── API Response Types ─────────────────────────────────────────
export interface CodeResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  execution_time_ms: number;
}

export interface SystemStatus {
  agent: string;
  version: string;
  status: string;
  environment: string;
  providers_configured: string[];
  uptime_seconds: number;
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

// ── Command Palette Actions ────────────────────────────────────
export interface CommandAction {
  id: string;
  label: string;
  shortcut?: string;
  icon?: string;
  action: () => void;
}
