// ═══════════════════════════════════════════════════════════════
// NEXUS — Settings Popover (Cmd+, to toggle)
// Enhanced V3: Voice, Memory, Capabilities sections
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Settings, Key, Zap, Shield, Bot, Wifi, WifiOff, X,
  Mic, MicOff, Volume2, VolumeX, Brain, Database, Trash2,
  Wrench, Sparkles, Globe, Layers, Server,
  ChevronDown, ChevronRight, Eye, EyeOff, Save, Loader2,
} from "lucide-react";
import { ThemeToggle } from "./theme-toggle";
import type { VoiceConfig, MemoryLayer } from "@/types/nexus";
import { useIsMobile } from "@/hooks/use-mobile";

// ── Providers (fetched dynamically from backend) ───────────

interface ProviderInfo {
  id: string;
  name: string;
  tier: "free" | "paid" | "local";
  models: string[];
  available: boolean;
  default_model: string;
}

const PROVIDER_META: Record<string, { name: string; tier: "free" | "paid" | "local"; models: string[] }> = {
  gemini:        { name: "Google AI",    tier: "free",  models: ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-2.5-pro-preview-05-06", "gemini-2.0-flash", "gemini-2.0-flash-lite"] },
  openai:        { name: "OpenAI",       tier: "paid",  models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  anthropic:     { name: "Anthropic",    tier: "paid",  models: ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"] },
  groq:          { name: "Groq",         tier: "free",  models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"] },
  openrouter:    { name: "OpenRouter",   tier: "paid",  models: ["openrouter/auto", "meta-llama/llama-4-maverick"] },
  nvidia:        { name: "NVIDIA",       tier: "free",  models: ["nvidia/llama-3.1-nemotron-70b-instruct"] },
  cerebras:      { name: "Cerebras",     tier: "free",  models: ["llama3.1-8b", "llama-3.3-70b"] },
  together:      { name: "Together",     tier: "paid",  models: ["meta-llama/Llama-3.3-70B-Instruct-Turbo"] },
  deepinfra:     { name: "DeepInfra",    tier: "free",  models: ["meta-llama/Llama-4-Maverick-17B"] },
  zhipuai:       { name: "ZhipuAI",      tier: "free",  models: ["glm-4-flash", "glm-4.5-flash"] },
  pollinations:  { name: "Pollinations", tier: "free",  models: ["openai"] },
  g4f:           { name: "G4F",          tier: "free",  models: ["gpt-4o-mini"] },
  ollama:        { name: "Ollama",       tier: "local", models: ["llama3.1:8b", "mistral", "codellama"] },
};

// ── Voice engines ──────────────────────────────────────────

const TTS_ENGINES = [
  { id: "edge" as const, name: "Edge TTS" },
  { id: "voicevox" as const, name: "VoiceVOX" },
];

const VOICES_EDGE = [
  "fr-FR-DeniseNeural",
  "fr-FR-HenriNeural",
  "fr-FR-EloiseNeural",
  "en-US-AriaNeural",
  "en-US-GuyNeural",
  "ja-JP-NanamiNeural",
];

const VOICES_VOICEVOX = [
  "四国めたん",
  "ずんだもん",
  "春日部つむぎ",
  "雨晴はう",
];

const LANGUAGES = [
  { id: "fr", name: "Francais" },
  { id: "en", name: "English" },
  { id: "ja", name: "日本語" },
];

// ── Memory layers ──────────────────────────────────────────

const MEMORY_LAYERS: { id: MemoryLayer; label: string; icon: typeof Brain }[] = [
  { id: "working", label: "Working", icon: Brain },
  { id: "episodic", label: "Episodic", icon: Layers },
  { id: "semantic", label: "Semantic", icon: Database },
  { id: "procedural", label: "Procedural", icon: Wrench },
  { id: "identity", label: "Identity", icon: Bot },
];

export function SettingsPopover() {
  const {
    settingsOpen, setSettingsOpen, provider, model, setProvider, setModel,
    agentMode, setAgentMode, avatarEnabled,
  avatarProfessionalMode, toggleAvatar, backendConnected,
    voiceConfig, setVoiceConfig, voiceState, setVoiceState,
    capabilities, crystallizedSkills,
  } = useNexusStore();

  // ── Local state ──
  const isMobile = useIsMobile();
  const [autoRead, setAutoRead] = useState(false);
  const [backendProviders, setBackendProviders] = useState<Record<string, { available: boolean; default_model: string }>>({});

  // ── API Keys state ──
  const [apiKeysOpen, setApiKeysOpen] = useState(false);
  const [apiKeysData, setApiKeysData] = useState<Record<string, { name: string; env_var: string; configured: boolean; masked: string }>>({});
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({});
  const [apiKeySaving, setApiKeySaving] = useState<string | null>(null);
  const [apiKeyShow, setApiKeyShow] = useState<Record<string, boolean>>({});
  const [apiKeyLoading, setApiKeyLoading] = useState(false);

  // ── Fetch providers from backend ──
  useEffect(() => {
    let active = true;
    const fetchProviders = async () => {
      try {
        const res = await fetch("/api/nexus/providers");
        if (!res.ok) return;
        const data = await res.json();
        if (active) setBackendProviders(data);
      } catch { /* silent */ }
    };
    fetchProviders();
    return () => { active = false; };
  }, []);

  // ── Build merged provider list (backend status + frontend meta) ──
  const providers: ProviderInfo[] = useMemo(() => {
    const ids = new Set([...Object.keys(PROVIDER_META), ...Object.keys(backendProviders)]);
    return Array.from(ids).map((id) => {
      const meta = PROVIDER_META[id];
      const backend = backendProviders[id];
      return {
        id,
        name: meta?.name ?? id,
        tier: meta?.tier ?? "paid",
        models: meta?.models ?? (backend?.default_model ? [backend.default_model] : []),
        available: backend?.available ?? false,
        default_model: backend?.default_model ?? meta?.models?.[0] ?? "",
      };
    }).sort((a, b) => {
      // Available providers first, then by tier (free > local > paid)
      if (a.available !== b.available) return a.available ? -1 : 1;
      const tierOrder = { free: 0, local: 1, paid: 2 };
      return (tierOrder[a.tier] ?? 2) - (tierOrder[b.tier] ?? 2);
    });
  }, [backendProviders]);

  // ── Models for selected provider ──
  const availableModels = useMemo(() => {
    const p = providers.find((pr) => pr.id === provider);
    return p?.models ?? [];
  }, [providers, provider]);

  // ── Derive available voices from engine (no setState in effect) ──
  const availableVoices = useMemo(
    () => (voiceConfig.engine === "edge" ? VOICES_EDGE : VOICES_VOICEVOX),
    [voiceConfig.engine]
  );

  // ── Memory counts from backend (only poll when open) ──
  const [memoryCounts, setMemoryCounts] = useState<Record<string, number>>({
    working: 0, episodic: 0, semantic: 0, procedural: 0, identity: 0,
  });

  useEffect(() => {
    if (!settingsOpen) return;
    let active = true;
    const fetchCounts = async () => {
      try {
        const res = await fetch("/api/nexus/memory/stats");
        if (!res.ok) return;
        const data = await res.json();
        if (active) setMemoryCounts(data.counts ?? data);
      } catch { /* silent */ }
    };
    fetchCounts();
    const interval = setInterval(fetchCounts, 10000);
    return () => { active = false; clearInterval(interval); };
  }, [settingsOpen]);

  // ── Fetch API keys from backend (only when section is opened) ──
  useEffect(() => {
    if (!apiKeysOpen) return;
    let active = true;
    setApiKeyLoading(true);
    fetch("/api/nexus/config/api-keys")
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (active && data) setApiKeysData(data);
      })
      .catch(() => {})
      .finally(() => { if (active) setApiKeyLoading(false); });
    return () => { active = false; };
  }, [apiKeysOpen]);

  // ── Save API key ──
  const handleSaveApiKey = useCallback(async (providerId: string) => {
    const keyValue = (apiKeyInputs[providerId] ?? "").trim();
    setApiKeySaving(providerId);
    try {
      const res = await fetch("/api/nexus/config/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, api_key: keyValue }),
      });
      if (res.ok) {
        const data = await res.json();
        setApiKeysData((prev) => ({
          ...prev,
          [providerId]: { ...prev[providerId], configured: data.configured, masked: data.masked },
        }));
        setApiKeyInputs((prev) => {
          const next = { ...prev };
          delete next[providerId];
          return next;
        });
        setApiKeyShow((prev) => ({ ...prev, [providerId]: false }));
      }
    } catch { /* silent */ }
    finally { setApiKeySaving(null); }
  }, [apiKeyInputs]);

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

  // ── Handlers ──
  const handleEngineChange = useCallback(
    (engine: string) => {
      const newEngine = engine as VoiceConfig["engine"];
      const defaultVoice = newEngine === "edge" ? VOICES_EDGE[0] : VOICES_VOICEVOX[0];
      setVoiceConfig({ ...voiceConfig, engine: newEngine, voice: defaultVoice });
    },
    [voiceConfig, setVoiceConfig]
  );

  const handleVoiceChange = useCallback(
    (voice: string) => {
      setVoiceConfig({ ...voiceConfig, voice });
    },
    [voiceConfig, setVoiceConfig]
  );

  const handleLanguageChange = useCallback(
    (language: string) => {
      setVoiceConfig({ ...voiceConfig, language });
    },
    [voiceConfig, setVoiceConfig]
  );

  const handleCompactMemory = useCallback(async () => {
    try {
      const res = await fetch("/api/nexus/memory/compact", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setMemoryCounts(data.counts ?? memoryCounts);
      }
    } catch { /* silent */ }
  }, [memoryCounts]);

  const handleClearWorking = useCallback(async () => {
    try {
      const res = await fetch("/api/nexus/memory/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ layer: "working" }),
      });
      if (res.ok) {
        setMemoryCounts((prev) => ({ ...prev, working: 0 }));
      }
    } catch { /* silent */ }
  }, []);

  // ── Capabilities counts ──
  const toolCount = capabilities?.tools.length ?? 0;
  const skillCount = capabilities?.skills.length ?? crystallizedSkills.length;
  const providerCount = capabilities?.providers.length ?? providers.length;
  const modelCount = capabilities?.models.length ?? 0;

  // ── Subsystem status ──
  const subsystems = [
    { name: "Backend", ok: backendConnected },
    { name: "Voice", ok: voiceState !== "error" },
    { name: "Memory", ok: true }, // assume ok
    { name: "LLM", ok: backendConnected },
  ];

  return (
    <Popover open={settingsOpen} onOpenChange={setSettingsOpen} modal={isMobile}>
      <PopoverTrigger asChild>
        <button
          aria-label="Ouvrir les parametres"
          className="fixed bottom-4 left-4 h-9 px-3 rounded-full bg-muted/40 backdrop-blur-sm border border-border/30 flex items-center gap-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors z-50 shadow-lg"
          title="Parametres (Cmd+,)"
        >
          <Settings size={14} />
          <span className="text-[11px] font-medium hidden sm:inline">Parametres</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className={`w-80 p-0 max-h-[70vh] overflow-y-auto ${isMobile ? "mobile-popover-fullscreen" : ""}`} side="top" align="start">
        {isMobile && (
          <div className="sticky top-0 flex items-center justify-between px-3 py-2 border-b border-border/15 bg-background z-10">
            <span className="text-xs font-medium">Paramètres</span>
            <button onClick={() => setSettingsOpen(false)} className="w-8 h-8 flex items-center justify-center rounded hover:bg-muted/30" aria-label="Fermer les paramètres">
              <X size={14} />
            </button>
          </div>
        )}
        <div className="p-3 space-y-3">
          {/* ── Connection ── */}
          <div className="flex items-center gap-2" role="status" aria-live="polite">
            {backendConnected ? (
              <Wifi size={12} className="text-emerald-500" />
            ) : (
              <WifiOff size={12} className="text-red-400" />
            )}
            <span className="text-[11px]">{backendConnected ? "Backend connecte" : "Deconnecte"}</span>
          </div>

          <Separator />

          {/* ── Mode ── */}
          <div className="grid grid-cols-2 gap-1.5" role="radiogroup" aria-label="Mode de l'agent">
            <button
              onClick={() => setAgentMode("plan")}
              role="radio"
              aria-checked={agentMode === "plan"}
              className={`flex items-center gap-1.5 p-2 rounded-md border text-[10px] transition-colors ${
                agentMode === "plan" ? "border-blue-500/40 bg-blue-500/10 text-blue-500" : "border-border/15 hover:bg-muted/20"
              }`}
            >
              <Shield size={11} /> Plan
            </button>
            <button
              onClick={() => setAgentMode("build")}
              role="radio"
              aria-checked={agentMode === "build"}
              className={`flex items-center gap-1.5 p-2 rounded-md border text-[10px] transition-colors ${
                agentMode === "build" ? "border-amber-500/40 bg-amber-500/10 text-amber-500" : "border-border/15 hover:bg-muted/20"
              }`}
            >
              <Zap size={11} /> Build
            </button>
          </div>

          {/* ── Avatar toggle ── */}
          <div className="flex items-center justify-between">
            <span className="text-[10px]">Avatar 3D</span>
            <button
              onClick={toggleAvatar}
              role="switch"
              aria-checked={avatarEnabled}
              aria-label={avatarEnabled ? "Desactiver l'avatar 3D" : "Activer l'avatar 3D"}
              className={`relative w-8 h-4 rounded-full transition-colors ${avatarEnabled ? "bg-primary" : "bg-muted"}`}
            >
              <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${avatarEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
          </div>

          {/* ── Theme toggle ── */}
          <div className="flex items-center justify-between">
            <span className="text-[10px]">Theme</span>
            <ThemeToggle />
          </div>

          <Separator />

          {/* ════════════════════════════════════════════════════════
              VOICE SECTION
              ════════════════════════════════════════════════════════ */}
          <div className="space-y-2">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Volume2 size={8} /> Voix
            </span>

            {/* TTS Engine selector */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground w-12 shrink-0">Moteur</span>
              <Select value={voiceConfig.engine} onValueChange={handleEngineChange}>
                <SelectTrigger className="h-6 text-[10px] flex-1" size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TTS_ENGINES.map((eng) => (
                    <SelectItem key={eng.id} value={eng.id} className="text-[10px]">
                      {eng.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Voice selector */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground w-12 shrink-0">Voix</span>
              <Select value={voiceConfig.voice} onValueChange={handleVoiceChange}>
                <SelectTrigger className="h-6 text-[10px] flex-1" size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableVoices.map((v) => (
                    <SelectItem key={v} value={v} className="text-[10px]">
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Language selector */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground w-12 shrink-0">Langue</span>
              <Select value={voiceConfig.language} onValueChange={handleLanguageChange}>
                <SelectTrigger className="h-6 text-[10px] flex-1" size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((l) => (
                    <SelectItem key={l.id} value={l.id} className="text-[10px]">
                      {l.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Auto-read toggle */}
            <div className="flex items-center justify-between">
              <span className="text-[10px]">Lecture auto</span>
              <button
                onClick={() => setAutoRead(!autoRead)}
                role="switch"
                aria-checked={autoRead}
                aria-label={autoRead ? "Desactiver la lecture automatique" : "Activer la lecture automatique"}
                className={`relative w-8 h-4 rounded-full transition-colors ${autoRead ? "bg-primary" : "bg-muted"}`}
              >
                <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${autoRead ? "translate-x-4" : "translate-x-0.5"}`} />
              </button>
            </div>
          </div>

          <Separator />

          {/* ════════════════════════════════════════════════════════
              MEMORY SECTION
              ════════════════════════════════════════════════════════ */}
          <div className="space-y-2">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Brain size={8} /> Memoire
            </span>

            {/* Memory layers with counts */}
            <div className="space-y-1">
              {MEMORY_LAYERS.map((layer) => {
                const Icon = layer.icon;
                const count = memoryCounts[layer.id] ?? 0;
                return (
                  <div
                    key={layer.id}
                    className="flex items-center gap-2 px-1.5 py-1 rounded-md hover:bg-muted/20 transition-colors"
                  >
                    <Icon size={10} className="text-muted-foreground shrink-0" />
                    <span className="text-[10px] flex-1">{layer.label}</span>
                    <Badge variant="secondary" className="h-3.5 text-[8px] px-1.5 font-mono">
                      {count}
                    </Badge>
                  </div>
                );
              })}
            </div>

            {/* Memory actions */}
            <div className="flex gap-1.5">
              <button
                onClick={handleCompactMemory}
                className="flex-1 flex items-center justify-center gap-1 p-1.5 rounded-md border border-border/15 text-[9px] text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors"
                title="Compacter la memoire"
              >
                <Database size={9} /> Compacter
              </button>
              <button
                onClick={handleClearWorking}
                className="flex-1 flex items-center justify-center gap-1 p-1.5 rounded-md border border-red-500/20 text-[9px] text-red-400/80 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Effacer la memoire de travail"
              >
                <Trash2 size={9} /> Effacer working
              </button>
            </div>
          </div>

          <Separator />

          {/* ── Provider ── */}
          <div className="space-y-1">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Key size={8} /> Fournisseur</span>
            <div className="max-h-40 overflow-y-auto space-y-0.5">
              {providers.map((p) => (
                <button
                  key={p.id}
                  onClick={() => { setProvider(p.id); setModel(p.default_model || p.models[0] || ""); }}
                  className={`w-full flex items-center gap-2 p-1.5 rounded-md text-[10px] transition-colors text-left ${
                    provider === p.id ? "bg-primary/10 text-primary" : "hover:bg-muted/20"
                  } ${!p.available ? "opacity-50" : ""}`}
                >
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    !p.available ? "bg-gray-500" :
                    p.tier === "free" ? "bg-emerald-500" : p.tier === "local" ? "bg-blue-500" : "bg-amber-500"
                  }`} />
                  <span className="flex-1">{p.name}</span>
                  <span className="text-[8px] text-muted-foreground">
                    {!p.available ? "cle manquante" : p.tier === "free" ? "gratuit" : p.tier}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* ── Model (dropdown) ── */}
          {availableModels.length > 0 ? (
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground w-12 shrink-0">Modele</span>
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger className="h-6 text-[10px] flex-1 font-mono" size="sm">
                  <SelectValue placeholder="Choisir un modele" />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.map((m) => (
                    <SelectItem key={m} value={m} className="text-[10px] font-mono">
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <Input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="h-6 text-[10px] font-mono"
              placeholder="Modele (tapez manuellement)"
            />
          )}

          <Separator />

          {/* ════════════════════════════════════════════════════════
              API KEYS SECTION (collapsible)
              ════════════════════════════════════════════════════════ */}
          <button
            onClick={() => setApiKeysOpen(!apiKeysOpen)}
            className="w-full flex items-center gap-1.5 text-[9px] text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
            aria-expanded={apiKeysOpen}
          >
            {apiKeysOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            <Key size={8} /> Cles API
          </button>

          {apiKeysOpen && (
            <div className="space-y-1.5 mt-1">
              {apiKeyLoading ? (
                <div className="flex items-center justify-center py-3">
                  <Loader2 size={14} className="animate-spin text-muted-foreground" />
                </div>
              ) : (
                Object.entries(apiKeysData).map(([id, info]) => {
                  const hasInput = (apiKeyInputs[id] ?? "").length > 0;
                  const showKey = apiKeyShow[id];
                  return (
                    <div key={id} className="rounded-md border border-border/15 p-1.5 space-y-1">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${info.configured ? "bg-emerald-500" : "bg-gray-500"}`} />
                        <span className="text-[10px] font-medium flex-1">{info.name}</span>
                        {info.configured && !hasInput && (
                          <span className="text-[8px] text-muted-foreground font-mono">{info.masked}</span>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <div className="flex-1 relative">
                          <Input
                            type={showKey ? "text" : "password"}
                            value={apiKeyInputs[id] ?? ""}
                            onChange={(e) => setApiKeyInputs((prev) => ({ ...prev, [id]: e.target.value }))}
                            className="h-6 text-[9px] font-mono pr-6"
                            placeholder={info.configured ? "Nouvelle cle..." : "Coller votre cle API..."}
                          />
                          <button
                            onClick={() => setApiKeyShow((prev) => ({ ...prev, [id]: !prev[id] }))}
                            className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label={showKey ? "Masquer" : "Afficher"}
                          >
                            {showKey ? <EyeOff size={9} /> : <Eye size={9} />}
                          </button>
                        </div>
                        <button
                          onClick={() => handleSaveApiKey(id)}
                          disabled={!hasInput || apiKeySaving === id}
                          className="h-6 px-2 rounded-md bg-primary/15 text-primary text-[9px] font-medium hover:bg-primary/25 disabled:opacity-40 transition-colors flex items-center gap-0.5"
                        >
                          {apiKeySaving === id ? <Loader2 size={8} className="animate-spin" /> : <Save size={8} />}
                          {apiKeySaving === id ? "" : "OK"}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
              <p className="text-[8px] text-muted-foreground/50 text-center pt-0.5">
                Les cles sont sauvegardees dans le fichier .env du backend
              </p>
            </div>
          )}

          <Separator />

          {/* ════════════════════════════════════════════════════════
              CAPABILITIES INDICATOR
              ════════════════════════════════════════════════════════ */}
          <div className="space-y-2">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Wrench size={8} /> Capacites
            </span>

            {/* Counts grid */}
            <div className="grid grid-cols-4 gap-1">
              <div className="flex flex-col items-center p-1 rounded-md bg-muted/10">
                <Wrench size={9} className="text-muted-foreground" />
                <span className="text-[10px] font-mono font-semibold">{toolCount}</span>
                <span className="text-[7px] text-muted-foreground">Outils</span>
              </div>
              <div className="flex flex-col items-center p-1 rounded-md bg-muted/10">
                <Sparkles size={9} className="text-muted-foreground" />
                <span className="text-[10px] font-mono font-semibold">{skillCount}</span>
                <span className="text-[7px] text-muted-foreground">Skills</span>
              </div>
              <div className="flex flex-col items-center p-1 rounded-md bg-muted/10">
                <Server size={9} className="text-muted-foreground" />
                <span className="text-[10px] font-mono font-semibold">{providerCount}</span>
                <span className="text-[7px] text-muted-foreground">Fourn.</span>
              </div>
              <div className="flex flex-col items-center p-1 rounded-md bg-muted/10">
                <Globe size={9} className="text-muted-foreground" />
                <span className="text-[10px] font-mono font-semibold">{modelCount || "-"}</span>
                <span className="text-[7px] text-muted-foreground">Modeles</span>
              </div>
            </div>

            {/* Subsystem status dots */}
            <div className="flex items-center gap-3">
              {subsystems.map((sys) => (
                <div key={sys.name} className="flex items-center gap-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${sys.ok ? "bg-emerald-500" : "bg-red-400"}`} />
                  <span className="text-[8px] text-muted-foreground">{sys.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
