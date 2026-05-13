// ═══════════════════════════════════════════════════════════════
// NEXUS — Settings Dialog (Modal, not a full panel!)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Settings, Key, Zap, Shield, Bot, Wifi, WifiOff,
} from "lucide-react";
import type { ProviderInfo } from "@/types/nexus";

const PROVIDER_LIST: ProviderInfo[] = [
  { id: "zhipuai", name: "ZhipuAI (Gratuit)", tier: "free", models: ["glm-4-flash", "glm-4.5-flash", "glm-4v-flash"], requiresKey: false },
  { id: "pollinations", name: "Pollinations.ai", tier: "free", models: ["openai", "mistral"], requiresKey: false },
  { id: "g4f", name: "G4F.dev", tier: "free", models: ["gpt-4", "gpt-3.5"], requiresKey: false },
  { id: "deepinfra", name: "DeepInfra", tier: "free", models: ["meta-llama/Llama-3"], requiresKey: false },
  { id: "gemini", name: "Google Gemini", tier: "free", models: ["gemini-2.5-flash", "gemini-2.5-pro"], requiresKey: true },
  { id: "openai", name: "OpenAI", tier: "paid", models: ["gpt-4o", "gpt-4o-mini"], requiresKey: true },
  { id: "anthropic", name: "Anthropic", tier: "paid", models: ["claude-sonnet-4-20250514"], requiresKey: true },
  { id: "ollama", name: "Ollama (local)", tier: "local", models: ["llama3.1:8b"], requiresKey: false },
];

export function SettingsDialog() {
  const {
    settingsOpen, setSettingsOpen, provider, model, setProvider, setModel,
    agentMode, setAgentMode, avatarEnabled, toggleAvatar, backendConnected,
  } = useNexusStore();

  return (
    <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-sm">
            <Settings size={14} />
            Parametres
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {/* Connection */}
          <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/20">
            {backendConnected ? (
              <Wifi size={16} className="text-emerald-500" />
            ) : (
              <WifiOff size={16} className="text-red-400" />
            )}
            <div>
              <p className="text-xs font-medium">Backend</p>
              <p className="text-[10px] text-muted-foreground">
                {backendConnected ? "Connecte au backend NEXUS" : "Deconnecte — lancez le backend"}
              </p>
            </div>
          </div>

          {/* Agent Mode */}
          <div>
            <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Mode Agent</label>
            <div className="grid grid-cols-2 gap-2 mt-1.5">
              <button
                onClick={() => setAgentMode("plan")}
                className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs transition-colors ${
                  agentMode === "plan" ? "border-blue-500/50 bg-blue-500/10 text-blue-500" : "border-border/20 hover:bg-muted/20"
                }`}
              >
                <Shield size={14} />
                <div className="text-left">
                  <p className="font-medium">Plan</p>
                  <p className="text-[9px] text-muted-foreground">Lecture seule</p>
                </div>
              </button>
              <button
                onClick={() => setAgentMode("build")}
                className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs transition-colors ${
                  agentMode === "build" ? "border-amber-500/50 bg-amber-500/10 text-amber-500" : "border-border/20 hover:bg-muted/20"
                }`}
              >
                <Zap size={14} />
                <div className="text-left">
                  <p className="font-medium">Build</p>
                  <p className="text-[9px] text-muted-foreground">Acces complet</p>
                </div>
              </button>
            </div>
          </div>

          <Separator />

          {/* Avatar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot size={14} className="text-muted-foreground" />
              <div>
                <p className="text-xs font-medium">Avatar</p>
                <p className="text-[10px] text-muted-foreground">Afficher dans le chat</p>
              </div>
            </div>
            <button
              onClick={toggleAvatar}
              className={`relative w-9 h-5 rounded-full transition-colors ${avatarEnabled ? "bg-primary" : "bg-muted"}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${avatarEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
          </div>

          <Separator />

          {/* Provider */}
          <div>
            <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Key size={10} /> Fournisseur LLM
            </label>
            <div className="space-y-1 mt-1.5">
              {PROVIDER_LIST.map((p) => {
                const isActive = provider === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => { setProvider(p.id); if (p.models[0]) setModel(p.models[0]); }}
                    className={`w-full flex items-center gap-2.5 p-2 rounded-lg border text-left text-xs transition-colors ${
                      isActive ? "border-primary/40 bg-primary/5" : "border-border/15 hover:bg-muted/20"
                    }`}
                  >
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      p.tier === "free" ? "bg-emerald-500" : p.tier === "local" ? "bg-blue-500" : "bg-amber-500"
                    }`} />
                    <span className="flex-1 truncate">{p.name}</span>
                    <Badge variant={p.tier === "free" ? "secondary" : p.tier === "local" ? "outline" : "default"} className="text-[8px] h-4">
                      {p.tier === "free" ? "Gratuit" : p.tier === "local" ? "Local" : "Payant"}
                    </Badge>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model */}
          <div>
            <label className="text-[11px] font-medium text-muted-foreground">Modele actif</label>
            <Input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="h-8 text-xs font-mono mt-1"
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
