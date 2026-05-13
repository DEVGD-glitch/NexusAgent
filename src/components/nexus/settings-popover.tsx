// ═══════════════════════════════════════════════════════════════
// NEXUS — Settings Popover (Cmd+, to toggle)
// Minimal popover, not a full dialog/page
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Settings, Key, Zap, Shield, Bot, Wifi, WifiOff, X,
} from "lucide-react";

const PROVIDERS = [
  { id: "zhipuai", name: "ZhipuAI", tier: "free" as const, models: ["glm-4-flash", "glm-4.5-flash"] },
  { id: "pollinations", name: "Pollinations", tier: "free" as const, models: ["openai"] },
  { id: "g4f", name: "G4F", tier: "free" as const, models: ["gpt-4"] },
  { id: "openai", name: "OpenAI", tier: "paid" as const, models: ["gpt-4o"] },
  { id: "anthropic", name: "Anthropic", tier: "paid" as const, models: ["claude-sonnet-4-20250514"] },
  { id: "ollama", name: "Ollama", tier: "local" as const, models: ["llama3.1:8b"] },
];

export function SettingsPopover() {
  const {
    settingsOpen, setSettingsOpen, provider, model, setProvider, setModel,
    agentMode, setAgentMode, avatarEnabled, toggleAvatar, backendConnected,
  } = useNexusStore();

  // Cmd+, shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") {
        e.preventDefault();
        setSettingsOpen(!settingsOpen);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [settingsOpen, setSettingsOpen]);

  return (
    <Popover open={settingsOpen} onOpenChange={setSettingsOpen}>
      <PopoverTrigger asChild>
        <button
          className="fixed bottom-4 left-4 w-8 h-8 rounded-full bg-muted/30 border border-border/20 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors z-50"
          title="Parametres (Cmd+,)"
        >
          <Settings size={14} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" side="top" align="start">
        <div className="p-3 space-y-3">
          {/* Connection */}
          <div className="flex items-center gap-2">
            {backendConnected ? (
              <Wifi size={12} className="text-emerald-500" />
            ) : (
              <WifiOff size={12} className="text-red-400" />
            )}
            <span className="text-[11px]">{backendConnected ? "Backend connecte" : "Deconnecte"}</span>
          </div>

          <Separator />

          {/* Mode */}
          <div className="grid grid-cols-2 gap-1.5">
            <button
              onClick={() => setAgentMode("plan")}
              className={`flex items-center gap-1.5 p-2 rounded-md border text-[10px] transition-colors ${
                agentMode === "plan" ? "border-blue-500/40 bg-blue-500/10 text-blue-500" : "border-border/15 hover:bg-muted/20"
              }`}
            >
              <Shield size={11} /> Plan
            </button>
            <button
              onClick={() => setAgentMode("build")}
              className={`flex items-center gap-1.5 p-2 rounded-md border text-[10px] transition-colors ${
                agentMode === "build" ? "border-amber-500/40 bg-amber-500/10 text-amber-500" : "border-border/15 hover:bg-muted/20"
              }`}
            >
              <Zap size={11} /> Build
            </button>
          </div>

          {/* Avatar toggle */}
          <div className="flex items-center justify-between">
            <span className="text-[10px]">Avatar 3D</span>
            <button
              onClick={toggleAvatar}
              className={`relative w-8 h-4 rounded-full transition-colors ${avatarEnabled ? "bg-primary" : "bg-muted"}`}
            >
              <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${avatarEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
          </div>

          <Separator />

          {/* Provider */}
          <div className="space-y-1">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Key size={8} /> Fournisseur</span>
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => { setProvider(p.id); if (p.models[0]) setModel(p.models[0]); }}
                className={`w-full flex items-center gap-2 p-1.5 rounded-md text-[10px] transition-colors text-left ${
                  provider === p.id ? "bg-primary/10 text-primary" : "hover:bg-muted/20"
                }`}
              >
                <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  p.tier === "free" ? "bg-emerald-500" : p.tier === "local" ? "bg-blue-500" : "bg-amber-500"
                }`} />
                <span className="flex-1">{p.name}</span>
                <span className="text-[8px] text-muted-foreground">{p.tier === "free" ? "gratuit" : p.tier}</span>
              </button>
            ))}
          </div>

          {/* Model */}
          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-6 text-[10px] font-mono"
            placeholder="Modele"
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
