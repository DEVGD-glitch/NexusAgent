"use client";

import { Button } from "@/components/ui/button";
import { useNexusStore, type PanelId } from "@/lib/nexus-store";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  LayoutDashboard, MessageSquare, ListChecks, Code2,
  Brain, Network, Wrench, Settings,
  PanelLeftClose, PanelLeft, Bot, Moon, Sun,
  Shield, Zap,
} from "lucide-react";

const PANELS: { id: PanelId; label: string; icon: React.ElementType }[] = [
  { id: "agents", label: "Agents Wall", icon: LayoutDashboard },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "tasks", label: "T\u00e2ches", icon: ListChecks },
  { id: "code", label: "Code", icon: Code2 },
  { id: "memory", label: "M\u00e9moire", icon: Brain },
  { id: "knowledge", label: "Connaissances", icon: Network },
  { id: "tools", label: "Outils", icon: Wrench },
  { id: "settings", label: "Config", icon: Settings },
];

export function Sidebar() {
  const {
    activePanel, setActivePanel,
    sidebarCollapsed, toggleSidebar,
    darkMode, toggleDarkMode,
    avatarEnabled, toggleAvatar,
    agentMode, setAgentMode,
  } = useNexusStore();

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 48 : 192 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        "flex flex-col border-r border-border bg-sidebar select-none shrink-0 h-full overflow-hidden",
        sidebarCollapsed ? "w-12" : "w-48"
      )}
    >
      <div className={cn(
        "flex items-center border-b border-border h-11",
        sidebarCollapsed ? "justify-center px-0" : "justify-between px-3"
      )}>
        {!sidebarCollapsed && (
          <span className="text-[10px] font-bold tracking-[0.15em] text-primary uppercase">NEXUS</span>
        )}
        {sidebarCollapsed && (
          <span className="text-[10px] font-bold tracking-[0.15em] text-primary uppercase">N</span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-6 shrink-0"
          onClick={toggleSidebar}
        >
          {sidebarCollapsed ? <PanelLeft size={14} /> : <PanelLeftClose size={14} />}
        </Button>
      </div>

      <nav className="flex-1 flex flex-col gap-0.5 p-1.5">
        {PANELS.map(({ id, label, icon: Icon }) => {
          const active = activePanel === id;
          return (
            <motion.div
              key={id}
              whileHover={{ scale: 1.04 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
            >
              <Button
                variant="ghost"
                className={cn(
                  "justify-start gap-2.5 h-8 px-2 text-xs font-normal rounded-sm transition-colors w-full",
                  sidebarCollapsed && "justify-center px-0",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                )}
                onClick={() => setActivePanel(id)}
              >
                <Icon size={15} className={cn("shrink-0", active && "text-primary")} />
                {!sidebarCollapsed && <span>{label}</span>}
              </Button>
            </motion.div>
          );
        })}
      </nav>

      <div className="flex flex-col gap-0.5 p-1.5 border-t border-border">
        <Button
          variant="ghost"
          className={cn(
            "justify-start gap-2.5 h-8 px-2 text-xs font-normal rounded-sm",
            sidebarCollapsed && "justify-center px-0",
            avatarEnabled && "text-primary"
          )}
          onClick={toggleAvatar}
        >
          <Bot size={15} className="shrink-0" />
          {!sidebarCollapsed && (
            <span className="flex items-center gap-1.5">
              Avatar
              <span className={cn(
                "inline-block size-1.5 rounded-full transition-colors",
                avatarEnabled ? "bg-emerald-500" : "bg-muted-foreground/40"
              )} />
            </span>
          )}
        </Button>

        <Button
          variant="ghost"
          className={cn(
            "justify-start gap-2.5 h-8 px-2 text-xs font-normal rounded-sm",
            sidebarCollapsed && "justify-center px-0"
          )}
          onClick={toggleDarkMode}
        >
          {darkMode ? <Sun size={15} className="shrink-0" /> : <Moon size={15} className="shrink-0" />}
          {!sidebarCollapsed && <span>{darkMode ? "Clair" : "Sombre"}</span>}
        </Button>

        <Button
          variant="ghost"
          className={cn(
            "justify-start gap-2.5 h-8 px-2 text-xs font-normal rounded-sm",
            sidebarCollapsed && "justify-center px-0"
          )}
          onClick={() => setAgentMode(agentMode === "plan" ? "build" : "plan")}
        >
          {agentMode === "plan" ? (
            <Shield size={15} className="shrink-0 text-chart-1" />
          ) : (
            <Zap size={15} className="shrink-0 text-chart-4" />
          )}
          {!sidebarCollapsed && (
            <span>{agentMode === "plan" ? "Plan" : "Build"}</span>
          )}
        </Button>
      </div>
    </motion.aside>
  );
}
