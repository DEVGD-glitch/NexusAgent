// ═══════════════════════════════════════════════════════════════
// NEXUS — Command Palette (Cmd+K)
// Quick access for power users — everything reachable from keyboard
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { Command } from "@/components/ui/command";
import {
  MessageSquare, Settings, Brain, BookOpen, Users,
  Shield, Zap, Terminal, Globe, Code2,
} from "lucide-react";

export function CommandPalette() {
  const { commandOpen, setCommandOpen, setSettingsOpen } = useNexusStore();
  const [search, setSearch] = useState("");

  const commands = [
    { id: "settings", label: "Ouvrir les parametres", icon: Settings, shortcut: "⌘,", action: () => { setSettingsOpen(true); setCommandOpen(false); } },
    { id: "mode-build", label: "Mode Build (acces complet)", icon: Zap, action: () => { useNexusStore.getState().setAgentMode("build"); setCommandOpen(false); } },
    { id: "mode-plan", label: "Mode Plan (lecture seule)", icon: Shield, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "toggle-avatar", label: "Activer/desactiver l'avatar 3D", icon: Users, action: () => { useNexusStore.getState().toggleAvatar(); setCommandOpen(false); } },
    { id: "ask-memory", label: "Poser une question a la memoire", icon: Brain, action: () => { setCommandOpen(false); /* focus input with /memory prefix */ } },
    { id: "web-search", label: "Rechercher sur le web", icon: Globe, action: () => { setCommandOpen(false); } },
    { id: "run-code", label: "Executer du code", icon: Terminal, action: () => { setCommandOpen(false); } },
    { id: "new-chat", label: "Nouvelle conversation", icon: MessageSquare, action: () => { useNexusStore.getState().addConversation(); setCommandOpen(false); } },
    { id: "knowledge", label: "Interroger le graphe de connaissances", icon: BookOpen, action: () => { setCommandOpen(false); } },
    { id: "spawn-agent", label: "Creer un agent", icon: Users, action: () => { setCommandOpen(false); } },
  ];

  const filtered = search
    ? commands.filter((c) => c.label.toLowerCase().includes(search.toLowerCase()))
    : commands;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen(!commandOpen);
        setSearch("");
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
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[25vh]">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCommandOpen(false)} />
      <div className="relative w-full max-w-md mx-4">
        <Command className="rounded-xl border border-border/30 shadow-2xl bg-card/95 backdrop-blur-md">
          <Command.Input
            placeholder="Tapez une commande..."
            value={search}
            onValueChange={setSearch}
            className="h-10 text-sm"
            autoFocus
          />
          <Command.List className="max-h-56 overflow-y-auto p-1">
            <Command.Empty className="py-3 text-center text-[11px] text-muted-foreground">
              Aucune commande
            </Command.Empty>
            {filtered.map((cmd) => (
              <Command.Item
                key={cmd.id}
                onSelect={cmd.action}
                className="flex items-center gap-3 px-3 py-1.5 rounded-lg cursor-pointer text-xs hover:bg-muted/30 aria-selected:bg-muted/30"
              >
                <cmd.icon size={13} className="text-muted-foreground shrink-0" />
                <span className="flex-1">{cmd.label}</span>
                {cmd.shortcut && (
                  <span className="text-[9px] text-muted-foreground/50 font-mono">{cmd.shortcut}</span>
                )}
              </Command.Item>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
