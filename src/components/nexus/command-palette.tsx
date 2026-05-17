"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import {
  Send, Sparkles, Shield, Zap, Settings, Bot, FileText,
  Palette, Globe, Mic, Volume2, Brain, Database, Trash2,
  Plus, Search, MessageSquare, BarChart3, HelpCircle,
  Moon, Sun, Monitor, X,
} from "lucide-react";
import { useTheme } from "next-themes";

interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
  group: string;
}

export function CommandPalette() {
  const {
    commandOpen, setCommandOpen,
    addConversation, setActiveView,
    setSettingsOpen, setAgentMode, agentMode,
    avatarEnabled, toggleAvatar,
    provider, setProvider, model, setModel,
    conversations, activeConversationId,
    voiceConfig, setVoiceConfig,
  } = useNexusStore();

  const { theme, setTheme } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    { id: "new-chat", label: "Nouvelle conversation", shortcut: "⌘N", icon: <Plus size={14} />, action: () => { addConversation(); setCommandOpen(false); }, group: "Navigation" },
    { id: "search-chats", label: "Rechercher conversations...", shortcut: "⌘K", icon: <Search size={14} />, action: () => { inputRef.current?.focus(); }, group: "Navigation" },
    { id: "settings", label: "Paramètres", shortcut: "⌘,", icon: <Settings size={14} />, action: () => { setSettingsOpen(true); setCommandOpen(false); }, group: "Navigation" },
    { id: "dashboard", label: "Dashboard", icon: <BarChart3 size={14} />, action: () => { setCommandOpen(false); }, group: "Navigation" },

    { id: "mode-plan", label: "Mode Plan", icon: <Shield size={14} />, action: () => { setAgentMode("plan"); setCommandOpen(false); }, group: "Mode Agent" },
    { id: "mode-build", label: "Mode Build", icon: <Zap size={14} />, action: () => { setAgentMode("build"); setCommandOpen(false); }, group: "Mode Agent" },

    { id: "provider-gemini", label: "Provider: Google AI (Gemini)", icon: <Bot size={14} />, action: () => { setProvider("gemini"); setModel("gemma-4-31b-it"); setCommandOpen(false); }, group: "Provider" },
    { id: "provider-openai", label: "Provider: OpenAI (GPT-4o)", icon: <Bot size={14} />, action: () => { setProvider("openai"); setModel("gpt-4o"); setCommandOpen(false); }, group: "Provider" },
    { id: "provider-anthropic", label: "Provider: Anthropic (Claude)", icon: <Bot size={14} />, action: () => { setProvider("anthropic"); setModel("claude-sonnet-4-20250514"); setCommandOpen(false); }, group: "Provider" },
    { id: "provider-groq", label: "Provider: Groq (Llama)", icon: <Bot size={14} />, action: () => { setProvider("groq"); setModel("llama-3.3-70b-versatile"); setCommandOpen(false); }, group: "Provider" },

    { id: "toggle-avatar", label: avatarEnabled ? "Masquer l'avatar" : "Afficher l'avatar", icon: <Bot size={14} />, action: () => { toggleAvatar(); setCommandOpen(false); }, group: "Avatar" },

    { id: "theme-light", label: "Thème: Clair", icon: <Sun size={14} />, action: () => { setTheme("light"); setCommandOpen(false); }, group: "Thème" },
    { id: "theme-dark", label: "Thème: Sombre", icon: <Moon size={14} />, action: () => { setTheme("dark"); setCommandOpen(false); }, group: "Thème" },
    { id: "theme-system", label: "Thème: Système", icon: <Monitor size={14} />, action: () => { setTheme("system"); setCommandOpen(false); }, group: "Thème" },

    { id: "voice-toggle", label: voiceConfig.engine === "edge" ? "Moteur: Edge TTS" : "Moteur: VoiceVOX", icon: <Volume2 size={14} />, action: () => { setVoiceConfig({ ...voiceConfig, engine: voiceConfig.engine === "edge" ? "voicevox" : "edge" }); setCommandOpen(false); }, group: "Voix" },

    { id: "help", label: "Aide & Raccourcis", icon: <HelpCircle size={14} />, action: () => { setCommandOpen(false); }, group: "Aide" },
  ];

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

  const grouped = commands.reduce<Record<string, CommandItem[]>>((acc, cmd) => {
    (acc[cmd.group] = acc[cmd.group] || []).push(cmd);
    return acc;
  }, {});

  return (
    <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
      <CommandInput ref={inputRef} placeholder="Tapez une commande ou recherchez..." />
      <CommandList>
        <CommandEmpty>Aucun résultat.</CommandEmpty>
        {Object.entries(grouped).map(([group, items]) => (
          <div key={group}>
            <CommandGroup heading={group}>
              {items.map((cmd) => (
                <CommandItem key={cmd.id} onSelect={cmd.action}>
                  <span className="mr-2 text-muted-foreground">{cmd.icon}</span>
                  <span className="flex-1">{cmd.label}</span>
                  {cmd.shortcut && (
                    <kbd className="ml-auto text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {cmd.shortcut}
                    </kbd>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </div>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
