// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Professional Sidebar
// ═══════════════════════════════════════════════════════════════

"use client";

import { useNexusStore } from "@/lib/nexus-store";
import type { PanelId } from "@/types/nexus";
import {
  MessageSquare, Users, Code2, Brain, BookOpen, Wrench,
  Shield, Settings, ChevronLeft, ChevronRight, Zap, ShieldCheck,
  Circle, Wifi, WifiOff,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const NAV_ITEMS: { id: PanelId; label: string; icon: React.ElementType }[] = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "agents", label: "Agents", icon: Users },
  { id: "code", label: "Code", icon: Code2 },
  { id: "memory", label: "Memoire", icon: Brain },
  { id: "knowledge", label: "Connaissances", icon: BookOpen },
  { id: "tools", label: "Outils", icon: Wrench },
  { id: "security", label: "Securite", icon: Shield },
  { id: "settings", label: "Parametres", icon: Settings },
];

export function NexusSidebar() {
  const { activePanel, setActivePanel, sidebarCollapsed, toggleSidebar, agentMode, agentStatus, backendConnected } = useNexusStore();

  return (
    <motion.aside
      className="flex flex-col h-full border-r border-border/50 bg-card/50 backdrop-blur-sm shrink-0 relative"
      animate={{ width: sidebarCollapsed ? 56 : 220 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-600 shrink-0">
          <Zap size={16} className="text-white" />
        </div>
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col min-w-0"
            >
              <span className="text-sm font-bold tracking-tight truncate">NEXUS</span>
              <span className="text-[10px] text-muted-foreground truncate">Agent IA Souverain</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Agent Mode Indicator */}
      <div className={`flex items-center gap-2 px-3 py-2 mx-2 mt-2 rounded-lg ${agentMode === "build" ? "bg-amber-500/10 text-amber-500" : "bg-blue-500/10 text-blue-500"}`}>
        {agentMode === "build" ? <Zap size={14} /> : <ShieldCheck size={14} />}
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-xs font-medium"
            >
              Mode {agentMode === "build" ? "Build" : "Plan"}
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = activePanel === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActivePanel(item.id)}
              className={`flex items-center gap-3 rounded-lg transition-all duration-150 group relative
                ${sidebarCollapsed ? "justify-center px-2 py-2.5" : "px-3 py-2"}
                ${isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary"
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              )}
              <item.icon size={18} className="shrink-0" />
              <AnimatePresence>
                {!sidebarCollapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-sm truncate"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          );
        })}
      </nav>

      {/* Footer — Connection Status */}
      <div className="px-2 pb-2 space-y-1">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${sidebarCollapsed ? "justify-center" : ""}`}>
          {backendConnected ? (
            <Wifi size={14} className="text-emerald-500" />
          ) : (
            <WifiOff size={14} className="text-red-400" />
          )}
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className={`text-[11px] ${backendConnected ? "text-emerald-500" : "text-red-400"}`}
              >
                {backendConnected ? "Backend connecte" : "Deconnecte"}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full py-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </motion.aside>
  );
}
