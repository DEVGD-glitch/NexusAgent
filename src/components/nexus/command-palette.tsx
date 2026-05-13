// ═══════════════════════════════════════════════════════════════
// NEXUS — Command Palette (Cmd+K / Ctrl+K)
// Quick access to all features without navigation
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect, useCallback } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { Command } from "@/components/ui/command";
import {
  MessageSquare, Code2, Settings, Brain, BookOpen, Users,
  Shield, Zap, Search, Activity, Terminal, Globe,
} from "lucide-react";

interface CommandItem {
  id: string;
  label: string;
  icon: React.ElementType;
  shortcut?: string;
  action: () => void;
}

export function CommandPalette() {
  const { commandOpen, setCommandOpen, setActiveView, setSettingsOpen, openContext } = useNexusStore();
  const [search, setSearch] = useState("");

  const commands: CommandItem[] = [
    { id: "chat", label: "Aller au Chat", icon: MessageSquare, shortcut: "G C", action: () => { setActiveView("chat"); setCommandOpen(false); } },
    { id: "code", label: "Aller au Code", icon: Code2, shortcut: "G X", action: () => { setActiveView("code"); setCommandOpen(false); } },
    { id: "settings", label: "Parametres", icon: Settings, shortcut: "G S", action: () => { setSettingsOpen(true); setCommandOpen(false); } },
    { id: "activity", label: "Voir l'activite agent", icon: Activity, action: () => { openContext("activity"); setCommandOpen(false); } },
    { id: "memory", label: "Rechercher dans la memoire", icon: Brain, action: () => { openContext("memory"); setCommandOpen(false); } },
    { id: "knowledge", label: "Graphe de connaissances", icon: BookOpen, action: () => { openContext("knowledge"); setCommandOpen(false); } },
    { id: "agents", label: "Gerer les agents", icon: Users, action: () => { openContext("agents"); setCommandOpen(false); } },
    { id: "mode-build", label: "Passer en mode Build", icon: Zap, action: () => { useNexusStore.getState().setAgentMode("build"); setCommandOpen(false); } },
    { id: "mode-plan", label: "Passer en mode Plan", icon: Shield, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "web-search", label: "Recherche web", icon: Globe, action: () => { openContext("knowledge"); setCommandOpen(false); } },
  ];

  const filtered = search
    ? commands.filter((c) => c.label.toLowerCase().includes(search.toLowerCase()))
    : commands;

  // Keyboard shortcut to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen(!commandOpen);
      }
      if (e.key === "Escape" && commandOpen) {
        setCommandOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [commandOpen, setCommandOpen]);

  if (!commandOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setCommandOpen(false)} />

      {/* Palette */}
      <div className="relative w-full max-w-lg mx-4">
        <Command className="rounded-xl border border-border/30 shadow-2xl bg-card/95 backdrop-blur-md">
          <Command.Input
            placeholder="Tapez une commande..."
            value={search}
            onValueChange={setSearch}
            className="h-11 text-sm"
            autoFocus
          />
          <Command.List className="max-h-64 overflow-y-auto p-1">
            <Command.Empty className="py-4 text-center text-xs text-muted-foreground">
              Aucune commande trouvee
            </Command.Empty>
            {filtered.map((cmd) => (
              <Command.Item
                key={cmd.id}
                onSelect={cmd.action}
                className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer text-sm hover:bg-muted/30 aria-selected:bg-muted/30"
              >
                <cmd.icon size={14} className="text-muted-foreground shrink-0" />
                <span className="flex-1">{cmd.label}</span>
                {cmd.shortcut && (
                  <span className="text-[10px] text-muted-foreground/60 font-mono">{cmd.shortcut}</span>
                )}
              </Command.Item>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
