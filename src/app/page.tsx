// ═══════════════════════════════════════════════════════════════
// NEXUS — Main Page (Chat-Centric Layout)
// Like Cursor/Windsurf: ActivityBar + Chat + ContextPanel
// ═══════════════════════════════════════════════════════════════

"use client";

import { useNexusStore } from "@/lib/nexus-store";
import { useNexusWebSocket } from "@/hooks/use-nexus-ws";
import { ActivityBar } from "@/components/nexus/activity-bar";
import { ChatView } from "@/components/nexus/chat-view";
import { CodeWorkspace } from "@/components/nexus/code-workspace";
import { ContextPanel } from "@/components/nexus/context-panel";
import { CommandPalette } from "@/components/nexus/command-palette";
import { SettingsDialog } from "@/components/nexus/settings-dialog";

export default function NexusApp() {
  const { activeView } = useNexusStore();

  // WebSocket for real-time agent events
  useNexusWebSocket();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Activity Bar (minimal left) */}
      <ActivityBar />

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 overflow-hidden">
        {activeView === "chat" && <ChatView />}
        {activeView === "code" && <CodeWorkspace />}
      </main>

      {/* Context Panel (slide-in right) */}
      <ContextPanel />

      {/* Overlays */}
      <CommandPalette />
      <SettingsDialog />
    </div>
  );
}
