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
} from "lucide-react";
import type { VoiceConfig, MemoryLayer } from "@/types/nexus";

const PROVIDERS = [
  { id: "zhipuai", name: "ZhipuAI", tier: "free" as const, models: ["glm-4-flash", "glm-4.5-flash"] },
  { id: "pollinations", name: "Pollinations", tier: "free" as const, models: ["openai"] },
  { id: "g4f", name: "G4F", tier: "free" as const, models: ["gpt-4"] },
  { id: "openai", name: "OpenAI", tier: "paid" as const, models: ["gpt-4o"] },
  { id: "anthropic", name: "Anthropic", tier: "paid" as const, models: ["claude-sonnet-4-20250514"] },
  { id: "ollama", name: "Ollama", tier: "local" as const, models: ["llama3.1:8b"] },
];

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
  avatarProfessionalMode,, toggleAvatar, backendConnected,
    voiceConfig, setVoiceConfig, voiceState, setVoiceState,
    capabilities, crystallizedSkills,
  } = useNexusStore();

  // ── Local state ──
  const [autoRead, setAutoRead] = useState(false);

  // ── Derive available voices from engine (no setState in effect) ──
  const availableVoices = useMemo(
    () => (voiceConfig.engine === "edge" ? VOICES_EDGE : VOICES_VOICEVOX),
    [voiceConfig.engine]
  );

  // ── Simulated memory counts (would come from backend) ──
  const memoryCounts: Record<string, number> = {
    working: 12,
    episodic: 47,
    semantic: 156,
    procedural: 23,
    identity: 5,
  };

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

  const handleCompactMemory = useCallback(() => {
    // In production, call /memory/compact endpoint
    console.log("[Nexus] Compacting memory...");
  }, []);

  const handleClearWorking = useCallback(() => {
    // In production, call /memory/clear?layer=working endpoint
    console.log("[Nexus] Clearing working memory...");
  }, []);

  // ── Capabilities counts ──
  const toolCount = capabilities?.tools.length ?? 0;
  const skillCount = capabilities?.skills.length ?? crystallizedSkills.length;
  const providerCount = capabilities?.providers.length ?? PROVIDERS.length;
  const modelCount = capabilities?.models.length ?? 0;

  // ── Subsystem status ──
  const subsystems = [
    { name: "Backend", ok: backendConnected },
    { name: "Voice", ok: voiceState !== "error" },
    { name: "Memory", ok: true }, // assume ok
    { name: "LLM", ok: backendConnected },
  ];

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
      <PopoverContent className="w-80 p-0 max-h-[70vh] overflow-y-auto" side="top" align="start">
        <div className="p-3 space-y-3">
          {/* ── Connection ── */}
          <div className="flex items-center gap-2">
            {backendConnected ? (
              <Wifi size={12} className="text-emerald-500" />
            ) : (
              <WifiOff size={12} className="text-red-400" />
            )}
            <span className="text-[11px]">{backendConnected ? "Backend connecte" : "Deconnecte"}</span>
          </div>

          <Separator />

          {/* ── Mode ── */}
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

          {/* ── Avatar toggle ── */}
          <div className="flex items-center justify-between">
            <span className="text-[10px]">Avatar 3D</span>
            <button
              onClick={toggleAvatar}
              className={`relative w-8 h-4 rounded-full transition-colors ${avatarEnabled,
  avatarProfessionalMode, ? "bg-primary" : "bg-muted"}`}
            >
              <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${avatarEnabled,
  avatarProfessionalMode, ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
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

          {/* ── Model ── */}
          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-6 text-[10px] font-mono"
            placeholder="Modele"
          />

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
