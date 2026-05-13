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

// ── Visualization (brick-by-brick) ─────────────────────────
export type VizEventType =
  | "viz_file_create" | "viz_file_edit" | "viz_file_delete" | "viz_dir_create"
  | "viz_code_write" | "viz_code_execute" | "viz_command_run"
  | "viz_build_step" | "viz_build_complete" | "viz_dependency_install"
  | "viz_test_run" | "viz_deploy_start" | "viz_artifact_render"
  | "viz_progress" | "viz_diff_preview" | "viz_file_tree_update" | "viz_error";

export interface VizEvent {
  id: string;
  type: VizEventType;
  timestamp: number;
  title: string;
  detail: string;
  path?: string;
  content?: string;
  language?: string;
  diff?: { old: string; new: string };
  progress: number;
  status: "pending" | "running" | "completed" | "error";
  artifact?: { type: "html" | "chart" | "image" | "document"; content: string };
  metadata: Record<string, unknown>;
  line_number?: number;
  total_lines?: number;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: FileTreeNode[];
  language?: string;
  size?: number;
}

// ── Artifacts ──────────────────────────────────────────────
export type ArtifactType = "html" | "chart" | "image" | "document" | "code" | "iframe";

export interface Artifact {
  id: string;
  type: ArtifactType;
  title: string;
  content: string;
  language?: string;
  createdAt: number;
}

// ── Voice ──────────────────────────────────────────────────
export type VoiceState = "idle" | "recording" | "transcribing" | "playing" | "error";

export interface Viseme {
  viseme: string;  // "A", "I", "U", "E", "O", "neutral"
  start: number;
  end: number;
}

export interface VoiceConfig {
  engine: "edge" | "voicevox";
  voice: string;
  language: string;
}

// ── Skills ─────────────────────────────────────────────────
export interface CrystallizedSkill {
  id: string;
  name: string;
  trigger_patterns: string[];
  steps: string[];
  success_rate: number;
  times_used: number;
  last_used: number;
  tags: string[];
}

// ── Multi-Agent ────────────────────────────────────────────
export type AgentModeV3 = "chat" | "plan" | "build" | "research" | "review";

export interface AgentSession {
  id: string;
  name: string;
  type: string;
  status: "running" | "completed" | "failed" | "pending" | "waiting_approval";
  task: string;
  progress: number;
  startedAt: number;
  completedAt?: number;
  model?: string;
  costUsd?: number;
}

// ── HITL Approval ──────────────────────────────────────────
export interface ApprovalRequest {
  id: string;
  agentId: string;
  toolName: string;
  args: Record<string, unknown>;
  riskLevel: "low" | "medium" | "high";
  createdAt: number;
}

// ── Capabilities (environment awareness) ───────────────────
export interface AgentCapabilities {
  tools: string[];
  skills: CrystallizedSkill[];
  memory_layers: string[];
  agent_types: string[];
  providers: string[];
  models: string[];
}

// ── Memory Layers ──────────────────────────────────────────
export type MemoryLayer = "working" | "episodic" | "semantic" | "procedural" | "identity";

export interface MemoryRecallResult {
  layer: MemoryLayer;
  content: string;
  relevance: number;
  timestamp: number;
}
