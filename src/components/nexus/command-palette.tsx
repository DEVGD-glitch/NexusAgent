// ═══════════════════════════════════════════════════════════════
// NEXUS — Command Palette (Cmd+K)
// Quick access for power users — everything reachable from keyboard
// Enhanced V3: mode switching, memory, skills, voice, crons, etc.
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandItem,
  CommandShortcut,
} from "@/components/ui/command";
import {
  MessageSquare, Settings, Brain, BookOpen, Users,
  Shield, Zap, Terminal, Globe, Code2,
  Mic, Database, Sparkles, Clock, Wrench, Eye, EyeOff,
  Trash2, User,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface CommandEntry {
  id: string;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
  action: () => void;
}

export function CommandPalette() {
  const {
    commandOpen, setCommandOpen, setSettingsOpen,
    avatarEnabled,
  } = useNexusStore();
  const [search, setSearch] = useState("");

  const commands: CommandEntry[] = [
    // ── Existing commands ──
    { id: "settings", label: "Ouvrir les parametres", icon: Settings, shortcut: "⌘,", action: () => { setSettingsOpen(true); setCommandOpen(false); } },
    { id: "mode-build", label: "Mode Build (acces complet)", icon: Zap, action: () => { useNexusStore.getState().setAgentMode("build"); setCommandOpen(false); } },
    { id: "mode-plan", label: "Mode Plan (lecture seule)", icon: Shield, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "toggle-avatar", label: "Activer/desactiver l'avatar 3D", icon: Users, action: () => { useNexusStore.getState().toggleAvatar(); setCommandOpen(false); } },
    { id: "vrm-hub", label: "Changer d'avatar VRM", icon: User, action: () => { useNexusStore.getState().setVrmHubOpen(true); setCommandOpen(false); } },
    { id: "ask-memory", label: "Poser une question a la memoire", icon: Brain, action: () => { setCommandOpen(false); document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus(); } },
    { id: "web-search", label: "Rechercher sur le web", icon: Globe, action: () => { setCommandOpen(false); document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus(); } },
    { id: "run-code", label: "Executer du code", icon: Terminal, action: () => { setCommandOpen(false); document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus(); } },
    { id: "new-chat", label: "Nouvelle conversation", icon: MessageSquare, action: () => { useNexusStore.getState().addConversation(); setCommandOpen(false); } },
    { id: "knowledge", label: "Interroger le graphe de connaissances", icon: BookOpen, action: () => { setCommandOpen(false); document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus(); } },
    { id: "spawn-agent", label: "Creer un agent", icon: Users, action: () => { setCommandOpen(false); document.querySelector<HTMLTextAreaElement>('[data-chat-input]')?.focus(); } },

    // ── New V3 commands ──
    { id: "mode-chat", label: "Mode Chat", icon: MessageSquare, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "mode-research", label: "Mode Recherche", icon: Globe, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "mode-review", label: "Mode Review", icon: Code2, action: () => { useNexusStore.getState().setAgentMode("plan"); setCommandOpen(false); } },
    { id: "memory-recall", label: "Rechercher dans la memoire", icon: Brain, action: () => { setCommandOpen(false); /* focus input with /memory prefix */ } },
    { id: "memory-compact", label: "Compacter la memoire", icon: Database, action: () => { setCommandOpen(false); /* call /memory/compact */ } },
    { id: "skill-list", label: "Lister les skills cristallises", icon: Sparkles, action: () => { setCommandOpen(false); /* show skills in context panel */ } },
    { id: "voice-toggle", label: "Activer/desactiver la voix", icon: Mic, action: () => {
      const currentState = useNexusStore.getState().voiceState;
      useNexusStore.getState().setVoiceState(currentState === "idle" ? "recording" : "idle");
      setCommandOpen(false);
    }},
    { id: "list-crons", label: "Voir les taches programmees", icon: Clock, action: () => { setCommandOpen(false); /* show crons in context panel */ } },
    { id: "capabilities", label: "Voir les capacites de l'agent", icon: Wrench, action: () => { setCommandOpen(false); /* show capabilities */ } },
    { id: "toggle-viz", label: "Afficher/masquer la visualisation", icon: avatarEnabled ? Eye : EyeOff, action: () => { setCommandOpen(false); /* toggle viz panel */ } },
    { id: "clear-chat", label: "Effacer la conversation", icon: Trash2, action: () => {
      // Clear current conversation messages
      const store = useNexusStore.getState();
      const convId = store.activeConversationId;
      if (convId) {
        useNexusStore.setState((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === convId ? { ...c, messages: [] } : c
          ),
        }));
      }
      setCommandOpen(false);
    }},
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
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[25vh]" role="dialog" aria-label="Palette de commandes" aria-modal="true">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCommandOpen(false)} />
      <div className="relative w-full max-w-md mx-4">
        <Command className="rounded-xl border border-border/30 shadow-2xl bg-card/95 backdrop-blur-md">
          <CommandInput
            placeholder="Tapez une commande..."
            value={search}
            onValueChange={setSearch}
            className="h-10 text-sm"
          />
          <CommandList className="max-h-64 overflow-y-auto p-1">
            <CommandEmpty className="py-3 text-center text-[11px] text-muted-foreground">
              Aucune commande
            </CommandEmpty>
            {filtered.map((cmd) => {
              const Icon = cmd.icon;
              return (
                <CommandItem
                  key={cmd.id}
                  onSelect={cmd.action}
                  className="flex items-center gap-3 px-3 py-1.5 rounded-lg cursor-pointer text-xs hover:bg-muted/30 aria-selected:bg-muted/30"
                >
                  <Icon size={13} className="text-muted-foreground shrink-0" />
                  <span className="flex-1">{cmd.label}</span>
                  {cmd.shortcut && (
                    <CommandShortcut className="text-[9px] text-muted-foreground/50 font-mono">
                      {cmd.shortcut}
                    </CommandShortcut>
                  )}
                </CommandItem>
              );
            })}
          </CommandList>
        </Command>
      </div>
    </div>
  );
}
