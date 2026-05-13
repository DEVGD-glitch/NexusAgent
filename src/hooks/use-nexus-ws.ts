// ═══════════════════════════════════════════════════════════════
// NEXUS — WebSocket Hook (Real-time Agent Events)
// Handles all V3 event types including viz, artifacts, voice,
// multi-agent, HITL approvals, streaming tokens, capabilities
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useRef, useCallback } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import type {
  AvatarExpression,
  VizEvent,
  ApprovalRequest,
  AgentCapabilities,
} from "@/types/nexus";

const WS_URL = process.env.NEXT_PUBLIC_NEXUS_WS || "ws://127.0.0.1:8081/ws";

interface WSEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

function uid(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

export function useNexusWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();
  const storeRef = useRef(useNexusStore.getState());
  // Ref for accumulating streaming tokens keyed by message/assistant turn
  const streamingRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    storeRef.current = useNexusStore.getState();
  });

  const handleEvent = useCallback((event: WSEvent) => {
    const store = storeRef.current;
    const { type, data } = event;

    switch (type) {
      // ── Core Agent Events ──────────────────────────────────────
      case "agent_thinking":
        store.setAgentStatus("thinking");
        store.setAvatarExpression("thinking");
        store.addActivity({ type: "agent_thinking", content: String(data.content || "En reflexion...") });
        break;

      case "agent_action":
        store.setAgentStatus("working");
        store.setAvatarExpression("joy");
        store.addActivity({ type: "agent_action", content: String(data.content || ""), toolName: String(data.tool || "") });
        break;

      case "tool_call":
        store.addActivity({ type: "tool_call", content: String(data.content || ""), toolName: String(data.tool || "") });
        break;

      case "tool_result":
        store.addActivity({ type: "tool_result", content: String(data.content || ""), toolName: String(data.tool || "") });
        break;

      case "file_create":
        store.setAvatarExpression("joy");
        store.addActivity({ type: "file_create", content: String(data.content || ""), details: String(data.path || "") });
        store.addBuildStep({
          type: "file_create", label: `Creation: ${data.path || "fichier"}`,
          detail: String(data.content || ""), status: "building", progress: 0, language: String(data.language || ""),
        });
        break;

      case "file_edit":
        store.addActivity({ type: "file_edit", content: String(data.content || ""), details: String(data.path || "") });
        store.addBuildStep({
          type: "file_edit", label: `Modification: ${data.path || "fichier"}`,
          detail: String(data.content || ""), status: "building", progress: 0, language: String(data.language || ""),
        });
        break;

      case "code_building":
        store.addBuildStep({
          type: "code_line", label: String(data.label || "Construction..."),
          detail: String(data.detail || ""), status: "building",
          progress: Number(data.progress || 0), language: String(data.language || ""), content: String(data.code || ""),
        });
        break;

      case "task_step":
        store.addActivity({ type: "task_step", content: String(data.content || ""), progress: Number(data.progress || 0) });
        break;

      case "task_done":
        store.setAgentStatus("idle");
        store.setAvatarExpression("joy");
        store.addActivity({ type: "task_done", content: String(data.content || "Tache terminee") });
        setTimeout(() => store.setAvatarExpression("neutral"), 3000);
        break;

      case "error":
        store.setAgentStatus("idle");
        store.setAvatarExpression("sad");
        store.addActivity({ type: "error", content: String(data.content || "Erreur") });
        setTimeout(() => store.setAvatarExpression("neutral"), 5000);
        break;

      case "avatar_expression":
        store.setAvatarExpression(String(data.expression || "neutral") as AvatarExpression);
        break;

      // ── Streaming Tokens (previously ignored) ──────────────────
      case "stream_token": {
        const tokenId = String(data.message_id || data.id || "current");
        const token = String(data.token || data.content || "");
        if (token) {
          const current = streamingRef.current.get(tokenId) || "";
          const updated = current + token;
          streamingRef.current.set(tokenId, updated);
          // We don't call addMessage per token — too expensive.
          // Instead we use a lightweight update via the store's streaming mechanism.
          // The ChatView reads this through the streamingContent state.
          store.addActivity({ type: "stream_token", content: token });
        }
        break;
      }

      // ── Visualization Events ───────────────────────────────────
      case "viz_event":
        store.addVizEvent(data as unknown as VizEvent);
        break;

      // ── Artifact Updates ───────────────────────────────────────
      case "artifact_update":
        store.addArtifact({
          id: uid(),
          type: String(data.type || "html") as "html" | "chart" | "image" | "document" | "code" | "iframe",
          title: String(data.title || "Artifact"),
          content: String(data.content || ""),
          createdAt: Date.now(),
        });
        break;

      // ── Voice Audio ────────────────────────────────────────────
      case "voice_audio": {
        // Play audio if TTS enabled
        const voiceState = store.voiceState;
        if (voiceState !== "recording" && voiceState !== "transcribing") {
          try {
            const audioBase64 = String(data.audio || data.content || "");
            if (audioBase64) {
              const audioBytes = atob(audioBase64);
              const audioArray = new Uint8Array(audioBytes.length);
              for (let i = 0; i < audioBytes.length; i++) {
                audioArray[i] = audioBytes.charCodeAt(i);
              }
              const blob = new Blob([audioArray], { type: String(data.mime_type || "audio/mp3") });
              const url = URL.createObjectURL(blob);
              const audio = new Audio(url);
              store.setVoiceState("playing");
              audio.onended = () => {
                store.setVoiceState("idle");
                URL.revokeObjectURL(url);
              };
              audio.onerror = () => {
                store.setVoiceState("idle");
                URL.revokeObjectURL(url);
              };
              audio.play().catch(() => {
                store.setVoiceState("idle");
                URL.revokeObjectURL(url);
              });
            }
          } catch {
            // Audio playback failed
          }
        }
        break;
      }

      // ── Avatar Visemes ─────────────────────────────────────────
      case "avatar_visemes":
        store.setCurrentVisemes(
          Array.isArray(data.visemes)
            ? data.visemes as { viseme: string; start: number; end: number }[]
            : []
        );
        break;

      // ── Multi-Agent ────────────────────────────────────────────
      case "agent_spawned": {
        const sessions = [...store.agentSessions];
        sessions.push({
          id: String(data.id || uid()),
          name: String(data.name || "Agent"),
          type: String(data.agent_type || data.type || "general"),
          status: "running",
          task: String(data.task || ""),
          progress: 0,
          startedAt: Date.now(),
        });
        store.setAgentSessions(sessions);
        break;
      }

      case "agent_completed": {
        const agentId = String(data.id || data.agent_id || "");
        if (agentId) {
          store.updateAgentSession(agentId, {
            status: data.error ? "failed" : "completed",
            progress: 100,
            completedAt: Date.now(),
            ...(data.result ? { task: String(data.result).slice(0, 200) } : {}),
          });
        }
        break;
      }

      // ── HITL Approval Requests ─────────────────────────────────
      case "approval_request":
        store.addApprovalRequest(data as unknown as ApprovalRequest);
        break;

      // ── Capabilities Update ────────────────────────────────────
      case "capabilities_update":
        store.setCapabilities(data as unknown as AgentCapabilities);
        break;

      default:
        // Unknown event type — ignore
        break;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      // Get auth token from localStorage if available
      const token = typeof window !== 'undefined' ? localStorage.getItem('nexus_token') : null;
      // Append token to WS URL for authentication
      const wsUrl = token ? `${WS_URL}?token=${encodeURIComponent(token)}` : WS_URL;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => { storeRef.current.setBackendConnected(true); };

      ws.onmessage = (event) => {
        try {
          handleEvent(JSON.parse(event.data));
        } catch (error) {
          console.warn('[WebSocket] Failed to parse event:', error);
        }
      };

      ws.onclose = () => {
        storeRef.current.setBackendConnected(false);
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        ws.close();
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      storeRef.current.setBackendConnected(false);
      reconnectRef.current = setTimeout(connect, 5000);
    }
  }, [handleEvent]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { send };
}
