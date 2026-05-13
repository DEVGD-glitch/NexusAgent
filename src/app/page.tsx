// ═══════════════════════════════════════════════════════════════
// NEXUS — Main Page (Pure Chat-Centric Layout)
// Avatar 3D + Chat = EVERYTHING. No sidebar. No panels.
// Cmd+K = Command Palette, Cmd+, = Settings
// ═══════════════════════════════════════════════════════════════

"use client";

import { useNexusStore } from "@/lib/nexus-store";
import { useNexusWebSocket } from "@/hooks/use-nexus-ws";
import { ChatView } from "@/components/nexus/chat-view";
import { CommandPalette } from "@/components/nexus/command-palette";
import { SettingsPopover } from "@/components/nexus/settings-popover";

export default function NexusApp() {
  // WebSocket for real-time agent events
  useNexusWebSocket();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* ── THE layout: just Chat (which includes Avatar) ── */}
      <ChatView />

      {/* ── Overlays (no visual space until invoked) ── */}
      <CommandPalette />
      <SettingsPopover />
    </div>
  );
}
