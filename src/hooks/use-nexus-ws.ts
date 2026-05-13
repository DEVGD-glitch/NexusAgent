// ═══════════════════════════════════════════════════════════════
// NEXUS Web — WebSocket Hook for Real-time Agent Events
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useRef, useCallback } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import type { AvatarExpression, BuildStep } from "@/types/nexus";

const WS_URL = process.env.NEXT_PUBLIC_NEXUS_WS || "ws://127.0.0.1:8081/ws";

interface WSEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export function useNexusWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();
  const storeRef = useRef(useNexusStore.getState());

  // Keep store ref updated
  useEffect(() => {
    storeRef.current = useNexusStore.getState();
  });

  const handleEvent = useCallback((event: WSEvent) => {
    const store = storeRef.current;
    const { type, data } = event;

    switch (type) {
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
          type: "file_create",
          label: `Creation: ${data.path || "fichier"}`,
          detail: String(data.content || ""),
          status: "building",
          progress: 0,
          language: String(data.language || ""),
        });
        break;

      case "file_edit":
        store.addActivity({ type: "file_edit", content: String(data.content || ""), details: String(data.path || "") });
        store.addBuildStep({
          type: "file_edit",
          label: `Modification: ${data.path || "fichier"}`,
          detail: String(data.content || ""),
          status: "building",
          progress: 0,
          language: String(data.language || ""),
        });
        break;

      case "code_building":
        store.addBuildStep({
          type: "code_line",
          label: String(data.label || "Construction..."),
          detail: String(data.detail || ""),
          status: "building",
          progress: Number(data.progress || 0),
          language: String(data.language || ""),
          content: String(data.code || ""),
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

      case "stream_token":
        break;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        storeRef.current.setBackendConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const wsEvent: WSEvent = JSON.parse(event.data);
          handleEvent(wsEvent);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        storeRef.current.setBackendConnected(false);
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
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
