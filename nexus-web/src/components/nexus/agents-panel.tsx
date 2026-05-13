"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import { api } from "@/lib/nexus-api";
import { Bot, Loader2, Sparkles } from "lucide-react";

const AGENT_TYPES = [
  { id: "general", label: "Général", desc: "Agent polyvalent" },
  { id: "researcher", label: "Chercheur", desc: "Recherche et synthèse d'informations" },
  { id: "developer", label: "Développeur", desc: "Écriture et débogage de code" },
  { id: "analyst", label: "Analyste", desc: "Analyse de données et reporting" },
  { id: "operator", label: "Opérateur", desc: "Automatisation système" },
];

const PATTERNS = [
  { id: "pipeline", label: "Pipeline", desc: "Chaîne séquentielle d'agents" },
  { id: "parallel", label: "Parallèle", desc: "Plusieurs agents en simultané" },
  { id: "supervisor", label: "Superviseur", desc: "Agent central délègue aux autres" },
  { id: "swarm", label: "Swarm", desc: "Collectif auto-organisé" },
];

export function AgentsPanel() {
  const [task, setTask] = useState("");
  const [agentType, setAgentType] = useState("general");
  const [pattern, setPattern] = useState("pipeline");
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<string[]>([]);

  async function handleSpawn() {
    if (!task.trim()) return;
    setLoading(true);
    try {
      const data = await api.spawnAgent(task, agentType);
      toast.success(`Agent ${data.agent_type} créé (${data.instance_id.slice(0, 8)}...)`);
      setTask("");
      setAgents((prev) => [...prev, data.instance_id]);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <Bot size={14} /> Agents
        </h2>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Type d'agent</p>
          <Select value={agentType} onValueChange={(v) => v && setAgentType(v)}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AGENT_TYPES.map((t) => (
                <SelectItem key={t.id} value={t.id} className="text-xs">
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Pattern d'orchestration</p>
          <Select value={pattern} onValueChange={(v) => v && setPattern(v)}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PATTERNS.map((p) => (
                <SelectItem key={p.id} value={p.id} className="text-xs">
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Tâche à confier</p>
          <Input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Décrivez la tâche..."
            className="h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && handleSpawn()}
          />
          <Button
            onClick={handleSpawn}
            disabled={loading || !task.trim()}
            size="sm"
            className="w-full h-8 gap-1 text-xs"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            Lancer l'agent
          </Button>
        </div>
      </div>

      <div className="flex-1">
        <ScrollArea className="h-full p-3">
          {agents.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">{agents.length} agent(s) lancé(s)</p>
              {agents.map((id) => (
                <Card key={id}>
                  <CardContent className="p-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Bot size={14} className="text-muted-foreground" />
                      <span className="text-xs font-mono">{id.slice(0, 12)}...</span>
                    </div>
                    <Badge variant="default" className="text-[10px]">Actif</Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              Lancez un agent pour voir son activité ici
            </p>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
