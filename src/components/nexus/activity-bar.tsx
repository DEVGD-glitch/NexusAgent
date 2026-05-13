// ═══════════════════════════════════════════════════════════════
// NEXUS — Activity Bar (Minimal, like Cursor/Windsurf)
// 3 icons only: Chat | Code | Settings
// ═══════════════════════════════════════════════════════════════

"use client";

import { useNexusStore } from "@/lib/nexus-store";
import { motion } from "framer-motion";
import { MessageSquare, Code2, Settings, Wifi, WifiOff, Zap, ShieldCheck } from "lucide-react";
import type { ViewId } from "@/types/nexus";

const NAV_ITEMS: { id: ViewId; icon: React.ElementType; label: string }[] = [
  { id: "chat", icon: MessageSquare, label: "Chat" },
  { id: "code", icon: Code2, label: "Code" },
];

export function ActivityBar() {
  const { activeView, setActiveView, setSettingsOpen, backendConnected, agentMode, agentStatus } = useNexusStore();

  return (
    <aside className="flex flex-col items-center w-12 h-full border-r border-border/30 bg-card/30 backdrop-blur-sm shrink-0 py-2 gap-1">
      {/* Logo */}
      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-600 mb-3 shrink-0">
        <Zap size={14} className="text-white" />
      </div>

      {/* Nav items */}
      {NAV_ITEMS.map((item) => {
        const isActive = activeView === item.id;
        const isWorking = item.id === "chat" && agentStatus !== "idle";
        return (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`relative flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-150 group
              ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground hover:bg-muted/30"}`}
            title={item.label}
          >
            {isActive && (
              <motion.div
                layoutId="activity-active"
                className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-r-full bg-primary"
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
            <item.icon size={18} className={isWorking ? "animate-pulse" : ""} />
          </button>
        );
      })}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Agent mode indicator */}
      <button
        onClick={() => {
          const store = useNexusStore.getState();
          store.setAgentMode(store.agentMode === "plan" ? "build" : "plan");
        }}
        className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors
          ${agentMode === "build" ? "text-amber-500 bg-amber-500/10" : "text-blue-500 bg-blue-500/10"}`}
        title={`Mode ${agentMode === "build" ? "Build" : "Plan"} — clic pour changer`}
      >
        {agentMode === "build" ? <Zap size={14} /> : <ShieldCheck size={14} />}
      </button>

      {/* Connection */}
      <div className="flex items-center justify-center w-8 h-8" title={backendConnected ? "Connecte" : "Deconnecte"}>
        {backendConnected ? (
          <Wifi size={13} className="text-emerald-500" />
        ) : (
          <WifiOff size={13} className="text-red-400/60" />
        )}
      </div>

      {/* Settings */}
      <button
        onClick={() => setSettingsOpen(true)}
        className="flex items-center justify-center w-9 h-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
        title="Parametres"
      >
        <Settings size={16} />
      </button>
    </aside>
  );
}
