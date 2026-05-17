"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Settings, Key, Zap, Shield, Bot, Wifi, WifiOff,
  Mic, Volume2, Brain, Database, Trash2,
  Wrench, Sparkles, Globe, Layers, Server,
  ChevronDown, ChevronRight, Eye, EyeOff, Save, Loader2,
  ArrowLeft, Palette, User, Bell,
} from "lucide-react";
import { ThemeToggle } from "@/components/nexus/theme-toggle";

const PROVIDERS = [
  { id: "gemini", name: "Google AI", tier: "free" },
  { id: "openai", name: "OpenAI", tier: "paid" },
  { id: "anthropic", name: "Anthropic", tier: "paid" },
  { id: "groq", name: "Groq", tier: "free" },
  { id: "openrouter", name: "OpenRouter", tier: "paid" },
  { id: "nvidia", name: "NVIDIA", tier: "free" },
  { id: "cerebras", name: "Cerebras", tier: "free" },
  { id: "together", name: "Together", tier: "paid" },
  { id: "deepinfra", name: "DeepInfra", tier: "free" },
  { id: "zhipuai", name: "ZhipuAI", tier: "free" },
  { id: "ollama", name: "Ollama", tier: "local" },
];

const MODELS_BY_PROVIDER: Record<string, string[]> = {
  gemini: ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-2.5-pro-preview-05-06", "gemini-2.0-flash"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
  anthropic: ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
  groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
  openrouter: ["openrouter/auto"],
  nvidia: ["nvidia/llama-3.1-nemotron-70b-instruct"],
  cerebras: ["llama3.1-8b", "llama-3.3-70b"],
  together: ["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
  deepinfra: ["meta-llama/Llama-4-Maverick-17B"],
  zhipuai: ["glm-4-flash", "glm-4.5-flash"],
  ollama: ["llama3.1:8b", "mistral"],
};

const VOICE_ENGINES = [
  { id: "edge", name: "Edge TTS" },
  { id: "voicevox", name: "VoiceVOX" },
];

const VOICES: Record<string, string[]> = {
  edge: ["fr-FR-DeniseNeural", "fr-FR-HenriNeural", "en-US-AriaNeural", "en-US-GuyNeural"],
  voicevox: ["四国めたん", "ずんだもん", "春日部つむぎ"],
};

const LANGUAGES = [
  { id: "fr", name: "Français" },
  { id: "en", name: "English" },
  { id: "ja", name: "日本語" },
];

type SettingsTab = "general" | "llm" | "voice" | "appearance" | "about";

export default function SettingsPage() {
  const {
    provider, model, setProvider, setModel,
    agentMode, setAgentMode, avatarEnabled, toggleAvatar,
    voiceConfig, setVoiceConfig, backendConnected,
    avatarProfessionalMode, setAvatarProfessionalMode,
  } = useNexusStore();

  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [providerStatus, setProviderStatus] = useState<Record<string, { available: boolean; default_model: string }>>({});

  useEffect(() => {
    fetch("/api/nexus/providers")
      .then(r => r.json())
      .then(d => setProviderStatus(d))
      .catch(() => {});
  }, []);

  const handleSaveApiKey = async (providerId: string) => {
    const key = apiKeys[providerId]?.trim();
    if (!key) return;
    setSaving(providerId);
    try {
      await fetch("/api/nexus/config/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, api_key: key }),
      });
      setApiKeys(prev => ({ ...prev, [providerId]: "" }));
    } catch {}
    finally { setSaving(null); }
  };

  const tabs: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
    { id: "general", label: "Général", icon: <Settings size={14} /> },
    { id: "llm", label: "LLM & Providers", icon: <Key size={14} /> },
    { id: "voice", label: "Voix", icon: <Volume2 size={14} /> },
    { id: "appearance", label: "Apparence", icon: <Palette size={14} /> },
    { id: "about", label: "À propos", icon: <Bot size={14} /> },
  ];

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-56 border-r border-border/15 p-4 space-y-1">
        <div className="flex items-center gap-2 mb-6 px-2">
          <ArrowLeft size={16} className="text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => window.history.back()} />
          <span className="text-sm font-semibold">Paramètres</span>
        </div>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.id
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        {activeTab === "general" && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Général</h2>
            <Separator />

            {/* Connection status */}
            <div className="flex items-center gap-2">
              {backendConnected ? <Wifi size={16} className="text-emerald-500" /> : <WifiOff size={16} className="text-red-400" />}
              <span className="text-sm">{backendConnected ? "Backend connecté" : "Déconnecté"}</span>
            </div>

            {/* Agent mode */}
            <div>
              <label className="text-sm font-medium mb-2 block">Mode de l'agent</label>
              <div className="grid grid-cols-2 gap-2">
                <button onClick={() => setAgentMode("plan")} className={`p-3 rounded-lg border text-sm ${agentMode === "plan" ? "border-blue-500 bg-blue-500/10 text-blue-500" : "border-border/20 hover:bg-muted/20"}`}>
                  <Shield size={16} className="mb-1" /> Plan
                </button>
                <button onClick={() => setAgentMode("build")} className={`p-3 rounded-lg border text-sm ${agentMode === "build" ? "border-amber-500 bg-amber-500/10 text-amber-500" : "border-border/20 hover:bg-muted/20"}`}>
                  <Zap size={16} className="mb-1" /> Build
                </button>
              </div>
            </div>

            {/* Avatar */}
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">Avatar 3D</span>
                <p className="text-xs text-muted-foreground">Afficher l'avatar holographique</p>
              </div>
              <button onClick={toggleAvatar} className={`relative w-11 h-6 rounded-full transition-colors ${avatarEnabled ? "bg-primary" : "bg-muted"}`}>
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${avatarEnabled ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>

            {/* Professional mode */}
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">Mode professionnel</span>
                <p className="text-xs text-muted-foreground">Masquer l'avatar, interface épurée</p>
              </div>
              <button onClick={() => setAvatarProfessionalMode(!avatarProfessionalMode)} className={`relative w-11 h-6 rounded-full transition-colors ${avatarProfessionalMode ? "bg-primary" : "bg-muted"}`}>
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${avatarProfessionalMode ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
          </div>
        )}

        {activeTab === "llm" && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">LLM & Providers</h2>
            <Separator />

            {/* Provider selection */}
            <div>
              <label className="text-sm font-medium mb-2 block">Fournisseur</label>
              <Select value={provider} onValueChange={(v) => { setProvider(v); setModel(MODELS_BY_PROVIDER[v]?.[0] || ""); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map(p => (
                    <SelectItem key={p.id} value={p.id}>
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${p.tier === "free" ? "bg-emerald-500" : p.tier === "local" ? "bg-blue-500" : "bg-amber-500"}`} />
                        {p.name}
                        <Badge variant="outline" className="text-[9px] h-4">{p.tier}</Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Model selection */}
            <div>
              <label className="text-sm font-medium mb-2 block">Modèle</label>
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(MODELS_BY_PROVIDER[provider] || []).map(m => (
                    <SelectItem key={m} value={m} className="font-mono text-xs">{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* API Keys */}
            <div>
              <label className="text-sm font-medium mb-3 block">Clés API</label>
              <div className="space-y-3">
                {PROVIDERS.filter(p => p.tier === "paid").map(p => (
                  <div key={p.id} className="rounded-lg border border-border/15 p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${providerStatus[p.id]?.available ? "bg-emerald-500" : "bg-gray-500"}`} />
                      <span className="text-sm font-medium flex-1">{p.name}</span>
                      {providerStatus[p.id]?.available && <Badge className="text-[9px] h-4">Connecté</Badge>}
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1 relative">
                        <Input
                          type={showKeys[p.id] ? "text" : "password"}
                          value={apiKeys[p.id] || ""}
                          onChange={(e) => setApiKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                          className="text-xs font-mono pr-8"
                          placeholder={`Clé ${p.name}...`}
                        />
                        <button onClick={() => setShowKeys(prev => ({ ...prev, [p.id]: !prev[p.id] }))} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground">
                          {showKeys[p.id] ? <EyeOff size={12} /> : <Eye size={12} />}
                        </button>
                      </div>
                      <Button size="sm" onClick={() => handleSaveApiKey(p.id)} disabled={!apiKeys[p.id]?.trim() || saving === p.id}>
                        {saving === p.id ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "voice" && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Voix</h2>
            <Separator />

            <div>
              <label className="text-sm font-medium mb-2 block">Moteur TTS</label>
              <Select value={voiceConfig.engine} onValueChange={(v) => setVoiceConfig({ ...voiceConfig, engine: v as any, voice: VOICES[v]?.[0] || "" })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {VOICE_ENGINES.map(e => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Voix</label>
              <Select value={voiceConfig.voice} onValueChange={(v) => setVoiceConfig({ ...voiceConfig, voice: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(VOICES[voiceConfig.engine] || []).map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Langue</label>
              <Select value={voiceConfig.language} onValueChange={(v) => setVoiceConfig({ ...voiceConfig, language: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map(l => <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {activeTab === "appearance" && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Apparence</h2>
            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">Thème</span>
                <p className="text-xs text-muted-foreground">Clair, sombre ou système</p>
              </div>
              <ThemeToggle />
            </div>
          </div>
        )}

        {activeTab === "about" && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">À propos</h2>
            <Separator />

            <div className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">NEXUS Agent</h3>
                <p className="text-sm text-muted-foreground">Agent IA Souverain — Zero Cloud, Zero Compromis</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-border/15 p-3">
                  <span className="text-xs text-muted-foreground">Version</span>
                  <p className="text-sm font-mono">1.0.0</p>
                </div>
                <div className="rounded-lg border border-border/15 p-3">
                  <span className="text-xs text-muted-foreground">Backend</span>
                  <p className={`text-sm ${backendConnected ? "text-emerald-500" : "text-red-400"}`}>{backendConnected ? "Connecté" : "Déconnecté"}</p>
                </div>
              </div>
              <div className="rounded-lg border border-border/15 p-3">
                <span className="text-xs text-muted-foreground">Fonctionnalités</span>
                <div className="flex flex-wrap gap-1 mt-2">
                  {["Multi-LLM", "5-Layer Memory", "MCP", "Voice", "Avatar 3D", "Workflows"].map(f => (
                    <Badge key={f} variant="secondary" className="text-[10px]">{f}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
