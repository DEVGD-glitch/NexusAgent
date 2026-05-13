// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Main Page (Agent-First Workspace)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useNexusStore } from "@/lib/nexus-store";
import { useNexusWebSocket } from "@/hooks/use-nexus-ws";
import { NexusSidebar } from "@/components/nexus/sidebar";
import { ChatPanel } from "@/components/nexus/chat-panel";
import { AgentsPanel } from "@/components/nexus/agents-panel";
import { CodePanel } from "@/components/nexus/code-panel";
import { MemoryPanel } from "@/components/nexus/memory-panel";
import { KnowledgePanel } from "@/components/nexus/knowledge-panel";
import { ToolsPanel } from "@/components/nexus/tools-panel";
import { SecurityPanel } from "@/components/nexus/security-panel";
import { SettingsPanel } from "@/components/nexus/settings-panel";
import type { PanelId } from "@/types/nexus";

const PANELS: Record<PanelId, React.ComponentType> = {
  chat: ChatPanel,
  agents: AgentsPanel,
  code: CodePanel,
  memory: MemoryPanel,
  knowledge: KnowledgePanel,
  tools: ToolsPanel,
  security: SecurityPanel,
  settings: SettingsPanel,
};

export default function NexusApp() {
  const { activePanel } = useNexusStore();

  // Initialize WebSocket connection for real-time events
  useNexusWebSocket();

  const Panel = PANELS[activePanel] || ChatPanel;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <NexusSidebar />
      <main className="flex-1 min-w-0 overflow-hidden">
        <Panel />
      </main>
    </div>
  );
}
