"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useNexusStore } from "@/lib/nexus-store";
import { api, type ProviderStatus } from "@/lib/nexus-api";
import { cn } from "@/lib/utils";
import {
  Wifi,
  CheckCircle2,
  XCircle,
  Loader2,
  Sun,
  Moon,
  Bot,
  Shield,
  Zap,
  RefreshCw,
} from "lucide-react";

const PROVIDERS = [
  { id: "pollinations", name: "Pollinations", group: "free-nokey", desc: "29 modèles, illimité" },
  { id: "g4f", name: "G4F", group: "free-nokey", desc: "200+ modèles" },
  { id: "deepinfra", name: "DeepInfra", group: "free-nokey", desc: "Modèles open-source" },
  { id: "gemini", name: "Gemini", group: "free-key", desc: "gemma-4-31b-it (défaut)" },
  { id: "groq", name: "Groq", group: "free-key", desc: "14k req/jour" },
  { id: "openrouter", name: "OpenRouter", group: "free-key", desc: "200+ modèles" },
  { id: "nvidia", name: "NVIDIA NIM", group: "free-key", desc: "100+ modèles" },
  { id: "cerebras", name: "Cerebras", group: "free-key", desc: "1M tokens/jour" },
  { id: "together", name: "Together", group: "free-key", desc: "Modèles open-source" },
  { id: "openai", name: "OpenAI", group: "paid", desc: "GPT-4, o3" },
  { id: "anthropic", name: "Anthropic", group: "paid", desc: "Claude 3/4" },
  { id: "glm", name: "GLM (Zhipu)", group: "paid", desc: "Zhipu AI" },
  { id: "ollama", name: "Ollama", group: "local", desc: "Modèles locaux" },
];

const GROUP_LABELS: Record<string, string> = {
  "free-nokey": "Gratuits (sans clé API)",
  "free-key": "Gratuits (avec clé API)",
  paid: "Payants",
  local: "Local",
};

export function SettingsPanel() {
  const {
    provider,
    setProvider,
    model,
    setModel,
    darkMode,
    toggleDarkMode,
    avatarEnabled,
    toggleAvatar,
    agentMode,
  } = useNexusStore();

  const [providerStatuses, setProviderStatuses] = useState<ProviderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; ms?: number } | null>(null);

  async function loadStatuses() {
    setLoading(true);
    try {
      const data = await api.providers();
      setProviderStatuses(data);
    } catch {
      setProviderStatuses(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatuses();
  }, []);

  async function handleTestConnection() {
    setTesting(provider);
    setTestResult(null);
    const start = performance.now();
    try {
      await api.providers();
      setTestResult({ ok: true, ms: Math.round(performance.now() - start) });
    } catch {
      setTestResult({ ok: false });
    } finally {
      setTesting(null);
    }
  }

  function getProviderStatus(id: string): { dot: string; label: string } {
    if (!providerStatuses) return { dot: "gray", label: "..." };
    const s = providerStatuses[id];
    if (!s) return { dot: "gray", label: "no data" };
    if (s.available) {
      if (PROVIDERS.find((p) => p.id === id)?.group === "free-nokey") {
        return { dot: "green", label: "gratuit" };
      }
      return { dot: "green", label: "online" };
    }
    const err = (s.last_error || "").toLowerCase();
    if (err.includes("no key") || err.includes("api key")) return { dot: "red", label: "no key" };
    return { dot: "red", label: "error" };
  }

  const grouped = PROVIDERS.reduce(
    (acc, p) => {
      (acc[p.group] ??= []).push(p);
      return acc;
    },
    {} as Record<string, typeof PROVIDERS>,
  );

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold flex items-center gap-1.5">
          <Zap size={14} /> Configuration
        </h2>
        <Button variant="outline" size="sm" onClick={loadStatuses} disabled={loading}>
          <RefreshCw size={12} className={cn("mr-1", loading && "animate-spin")} />
          Tester
        </Button>
      </div>

      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <Bot size={14} /> Model &amp; Provider
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0 space-y-3">
          <div>
            <Label className="text-xs">Provider</Label>
            <Select value={provider} onValueChange={(v) => v && setProvider(v)}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Sélectionner un provider" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(grouped).map(([group, providers]) => (
                  <SelectGroup key={group}>
                    <SelectLabel className="text-xs text-muted-foreground font-medium">
                      {GROUP_LABELS[group]}
                    </SelectLabel>
                    {providers.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        <span className="flex items-center justify-between w-full gap-2">
                          <span>{p.name}</span>
                          <span className="text-xs text-muted-foreground">{p.desc}</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Modèle</Label>
            <div className="flex gap-2 mt-1">
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="text-sm flex-1"
                placeholder="gemma-4-31b-it"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestConnection}
                disabled={testing !== null}
                className="shrink-0"
              >
                {testing !== null ? (
                  <Loader2 size={12} className="animate-spin mr-1" />
                ) : (
                  <Zap size={12} className="mr-1" />
                )}
                Test
              </Button>
            </div>
          </div>

          {testResult && (
            <div
              className={cn(
                "flex items-center gap-1.5 text-xs",
                testResult.ok ? "text-green-500" : "text-red-500",
              )}
            >
              {testResult.ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
              {testResult.ok ? `Connecté — ${testResult.ms}ms` : "Échec de connexion"}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <Wifi size={14} /> Statut des providers
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
              <Loader2 size={12} className="animate-spin" /> Chargement...
            </div>
          ) : (
            <ScrollArea className="h-[260px] pr-2">
              <div className="space-y-0.5">
                {PROVIDERS.map((p) => {
                  const st = getProviderStatus(p.id);
                  return (
                    <div
                      key={p.id}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/50 text-xs"
                    >
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full shrink-0",
                          st.dot === "green" && "bg-green-500",
                          st.dot === "red" && "bg-red-500",
                          st.dot === "gray" && "bg-muted-foreground/40",
                        )}
                      />
                      <span className="font-medium w-28 shrink-0">{p.name}</span>
                      <span className="text-muted-foreground flex-1 truncate">
                        {providerStatuses?.[p.id]?.default_model || "—"}
                      </span>
                      <Badge
                        variant={st.dot === "green" ? "default" : "secondary"}
                        className={cn(
                          "text-[10px] px-1.5 py-0 shrink-0",
                          st.dot === "red" &&
                            "bg-red-500/10 text-red-500 hover:bg-red-500/20",
                        )}
                      >
                        {st.label}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <Sun size={14} /> Apparence
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0 space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs flex items-center gap-1.5">
              {darkMode ? <Moon size={12} /> : <Sun size={12} />}
              Thème
            </Label>
            <Switch checked={darkMode} onCheckedChange={toggleDarkMode} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <Label className="text-xs flex items-center gap-1.5">
              <Bot size={12} />
              Avatar VRM
            </Label>
            <Switch checked={avatarEnabled} onCheckedChange={toggleAvatar} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <Label className="text-xs flex items-center gap-1.5">
              <Shield size={12} />
              Mode agent
            </Label>
            <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
              {agentMode}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
