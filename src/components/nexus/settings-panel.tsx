// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Settings Panel (Provider Config, Avatar, Mode)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Settings, Key, Monitor, Bot, Zap, Shield, Wifi, WifiOff } from "lucide-react";

const PROVIDER_LIST = [
  { id: "gemini", name: "Google Gemini", tier: "free", requiresKey: true, models: ["gemini-2.5-flash", "gemini-2.5-pro"] },
  { id: "pollinations", name: "Pollinations.ai", tier: "free", requiresKey: false, models: ["openai", "mistral"] },
  { id: "g4f", name: "G4F.dev", tier: "free", requiresKey: false, models: ["gpt-4", "gpt-3.5"] },
  { id: "deepinfra", name: "DeepInfra", tier: "free", requiresKey: false, models: ["meta-llama/Llama-3"] },
  { id: "openai", name: "OpenAI", tier: "paid", requiresKey: true, models: ["gpt-4o", "gpt-4o-mini"] },
  { id: "anthropic", name: "Anthropic", tier: "paid", requiresKey: true, models: ["claude-sonnet-4-20250514"] },
  { id: "groq", name: "Groq", tier: "paid", requiresKey: true, models: ["llama-3.1-70b"] },
  { id: "ollama", name: "Ollama (local)", tier: "local", requiresKey: false, models: ["llama3.1:8b"] },
];

export function SettingsPanel() {
  const { provider, model, setProvider, setModel, avatarEnabled, toggleAvatar, agentMode, setAgentMode, backendConnected } = useNexusStore();
  const [providerStatus, setProviderStatus] = useState<Record<string, { available: boolean; default_model: string }>>({});

  useEffect(() => {
    nexusApi.providers().then(setProviderStatus).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Settings size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Parametres</h1>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Connection */}
        <Card className="border-border/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              {backendConnected ? (
                <Wifi size={20} className="text-emerald-500" />
              ) : (
                <WifiOff size={20} className="text-red-400" />
              )}
              <div>
                <p className="text-sm font-medium">Backend</p>
                <p className="text-xs text-muted-foreground">
                  {backendConnected ? "Connecte au backend NEXUS" : "Deconnecte — lancez le backend"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Agent Mode */}
        <Card className="border-border/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2"><Zap size={14} />Mode Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setAgentMode("plan")}
                className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${
                  agentMode === "plan" ? "border-blue-500/50 bg-blue-500/10 text-blue-500" : "border-border/30 hover:bg-muted/20"
                }`}
              >
                <Shield size={16} />
                <div className="text-left">
                  <p className="text-xs font-medium">Plan</p>
                  <p className="text-[10px] text-muted-foreground">Lecture seule</p>
                </div>
              </button>
              <button
                onClick={() => setAgentMode("build")}
                className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${
                  agentMode === "build" ? "border-amber-500/50 bg-amber-500/10 text-amber-500" : "border-border/30 hover:bg-muted/20"
                }`}
              >
                <Zap size={16} />
                <div className="text-left">
                  <p className="text-xs font-medium">Build</p>
                  <p className="text-[10px] text-muted-foreground">Acces complet</p>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Avatar */}
        <Card className="border-border/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2"><Bot size={14} />Avatar</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm">Avatar NEXUS</p>
                <p className="text-xs text-muted-foreground">Afficher l'avatar dans le chat</p>
              </div>
              <button
                onClick={toggleAvatar}
                className={`relative w-10 h-5 rounded-full transition-colors ${avatarEnabled ? "bg-primary" : "bg-muted"}`}
              >
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${avatarEnabled ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Provider Configuration */}
        <Card className="border-border/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2"><Key size={14} />Fournisseurs LLM</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {PROVIDER_LIST.map((p) => {
                const status = providerStatus[p.id];
                const isActive = provider === p.id;

                return (
                  <button
                    key={p.id}
                    onClick={() => { setProvider(p.id); if (p.models[0]) setModel(p.models[0]); }}
                    className={`w-full flex items-center gap-3 p-2.5 rounded-lg border transition-colors text-left ${
                      isActive ? "border-primary/50 bg-primary/5" : "border-border/20 hover:bg-muted/20"
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full shrink-0 ${
                      status?.available ? "bg-emerald-500" : p.requiresKey ? "bg-muted-foreground/30" : "bg-amber-500"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium truncate">{p.name}</span>
                        <Badge variant={p.tier === "free" ? "secondary" : p.tier === "local" ? "outline" : "default"} className="text-[9px]">
                          {p.tier === "free" ? "Gratuit" : p.tier === "local" ? "Local" : "Payant"}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-muted-foreground">
                        {p.models.slice(0, 2).join(", ")}
                      </p>
                    </div>
                    {isActive && <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />}
                  </button>
                );
              })}
            </div>

            {/* Model selector */}
            <div className="mt-3">
              <label className="text-xs text-muted-foreground">Modele actif</label>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full h-8 mt-1 rounded-md border border-border/40 bg-muted/20 px-2 text-xs font-mono"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
