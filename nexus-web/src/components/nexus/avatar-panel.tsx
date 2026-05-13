"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { api } from "@/lib/nexus-api";
import { Play, Square, Mic, Volume2, Loader2, Bot } from "lucide-react";

export function AvatarPanel() {
  const [running, setRunning] = useState(false);
  const [vrmPath, setVrmPath] = useState("");
  const [speakText, setSpeakText] = useState("");
  const [loading, setLoading] = useState("");
  const [voices, setVoices] = useState<string[]>([]);
  const [expression, setExpression] = useState("neutral");

  async function handleStart() {
    setLoading("start");
    try {
      const res = await api.genericTool("avatar_start", vrmPath ? { vrm_path: vrmPath } : {});
      setRunning(true);
      toast.success("Avatar démarré");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading("");
    }
  }

  async function handleSpeak() {
    if (!speakText.trim()) return;
    setLoading("speak");
    try {
      await api.genericTool("avatar_speak", { text: speakText, expression });
      setSpeakText("");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading("");
    }
  }

  async function handleListVoices() {
    setLoading("voices");
    try {
      const data = await api.genericTool("avatar_list_voices");
      const list = Array.isArray(data) ? data : [];
      setVoices(list as string[]);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading("");
    }
  }

  async function handleSetExpression(expr: string) {
    setExpression(expr);
    if (running) {
      try {
        await api.genericTool("avatar_set_expression", { expression: expr });
      } catch { /* ignore */ }
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-56 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <Bot size={14} /> Avatar
        </h2>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Contrôle</p>
          {!running ? (
            <Button
              onClick={handleStart}
              disabled={loading === "start"}
              size="sm"
              className="w-full h-8 gap-1 text-xs"
            >
              {loading === "start" ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
              Démarrer l'avatar
            </Button>
          ) : (
            <Button variant="destructive" size="sm" className="w-full h-8 gap-1 text-xs">
              <Square size={12} /> Arrêter
            </Button>
          )}
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Expression</p>
          <div className="grid grid-cols-2 gap-1">
            {["neutral", "joy", "sad", "angry", "surprise", "relaxed"].map((expr) => (
              <Button
                key={expr}
                variant={expression === expr ? "secondary" : "ghost"}
                size="sm"
                className="h-7 text-[10px] capitalize"
                onClick={() => handleSetExpression(expr)}
              >
                {expr}
              </Button>
            ))}
          </div>
        </div>

        <Separator />

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">VRM Model</p>
          <Input
            value={vrmPath}
            onChange={(e) => setVrmPath(e.target.value)}
            placeholder="chemin/vers/model.vrm"
            className="h-8 text-xs"
          />
          <Button
            onClick={handleListVoices}
            disabled={loading === "voices"}
            variant="outline"
            size="sm"
            className="w-full h-7 gap-1 text-xs"
          >
            {loading === "voices" ? <Loader2 size={12} className="animate-spin" /> : <Volume2 size={12} />}
            Voir les voix
          </Button>
        </div>

        {voices.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Voix disponibles</p>
            <ScrollArea className="h-24">
              <div className="space-y-0.5">
                {voices.map((v) => (
                  <div key={v} className="text-xs text-muted-foreground truncate">{v}</div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <h3 className="text-sm font-medium">Synthèse vocale</h3>
          {running && <Badge variant="default" className="text-[10px]">Avatar actif</Badge>}
        </div>

        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="w-48 h-48 rounded-2xl bg-muted flex items-center justify-center mb-6 border border-border">
            <Bot size={64} className="text-muted-foreground/40" />
          </div>

          <div className="w-full max-w-md space-y-3">
            <Textarea
              value={speakText}
              onChange={(e) => setSpeakText(e.target.value)}
              placeholder="Texte a dire par l'avatar..."
              className="min-h-[80px] text-sm resize-none"
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSpeak())}
            />
            <Button
              onClick={handleSpeak}
              disabled={loading === "speak" || !speakText.trim() || !running}
              className="w-full gap-1"
            >
              {loading === "speak" ? (
                <><Loader2 size={14} className="animate-spin" /> Synthèse en cours...</>
              ) : (
                <><Mic size={14} /> Parler</>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
