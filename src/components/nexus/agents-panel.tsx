// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Agents Panel (Command Center)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { NexusAvatar } from "./avatar";
import { motion } from "framer-motion";
import { Users, Plus, Loader2, Check, X, Clock, User } from "lucide-react";

export function AgentsPanel() {
  const { agents, addAgent, updateAgentStatus, avatarExpression } = useNexusStore();
  const [agentTypes, setAgentTypes] = useState<string[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [spawning, setSpawning] = useState(false);
  const [taskInput, setTaskInput] = useState("");

  useEffect(() => {
    nexusApi.listAgents().then((data) => {
      setAgentTypes(data.types);
      setStats(data.stats);
    }).catch(() => {});
  }, []);

  const handleSpawn = async () => {
    if (!taskInput.trim()) return;
    setSpawning(true);
    try {
      const result = await nexusApi.spawnAgent(taskInput);
      addAgent({
        id: result.instance_id,
        name: `${result.agent_type}-${result.instance_id.slice(0, 6)}`,
        type: result.agent_type,
        status: "running",
        task: taskInput,
        progress: 0,
        startedAt: Date.now(),
      });
      setTaskInput("");
    } catch (err) {
      console.error("Spawn failed:", err);
    } finally {
      setSpawning(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Centre de Commandement</h1>
        </div>
        <Badge variant="outline" className="text-[10px]">
          {agents.filter(a => a.status === "running").length} actif{agents.filter(a => a.status === "running").length > 1 ? "s" : ""}
        </Badge>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Spawn new agent */}
        <Card className="border-border/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Plus size={14} className="text-primary" />
              Nouvel Agent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <input
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                placeholder="Decrivez la tache pour l'agent..."
                className="flex-1 h-9 rounded-md border border-border/40 bg-muted/20 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
                onKeyDown={(e) => e.key === "Enter" && handleSpawn()}
              />
              <Button onClick={handleSpawn} disabled={spawning || !taskInput.trim()} size="sm" className="gap-1.5">
                {spawning ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                Lancer
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Agent Types */}
        {agentTypes.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Types disponibles</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {agentTypes.map((type) => (
                <div key={type} className="flex items-center gap-2 p-2 rounded-lg border border-border/30 bg-muted/10">
                  <User size={14} className="text-primary shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium capitalize truncate">{type}</p>
                    <p className="text-[10px] text-muted-foreground">{stats[type] || 0} instance(s)</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Agents */}
        {agents.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Agents en cours</h3>
            {agents.map((agent) => (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card className="border-border/30">
                  <CardContent className="p-3">
                    <div className="flex items-start gap-3">
                      <NexusAvatar
                        expression={agent.status === "running" ? "thinking" : agent.status === "completed" ? "joy" : "neutral"}
                        thinking={agent.status === "running"}
                        size={36}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">{agent.name}</span>
                          <Badge variant={agent.status === "running" ? "default" : agent.status === "completed" ? "secondary" : "destructive"} className="text-[10px]">
                            {agent.status === "running" ? "En cours" : agent.status === "completed" ? "Termine" : "Echoue"}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">{agent.task}</p>
                        {agent.status === "running" && (
                          <Progress value={agent.progress} className="w-full h-1 mt-2" />
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {agents.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Users size={32} className="mb-3 opacity-30" />
            <p className="text-sm">Aucun agent actif</p>
            <p className="text-xs mt-1">Lancez une tache pour creer un agent</p>
          </div>
        )}
      </div>
    </div>
  );
}
