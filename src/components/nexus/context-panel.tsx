// ═══════════════════════════════════════════════════════════════
// NEXUS — Context Panel (right sidebar, slides in)
// Shows: Activity | Memory | Knowledge | Agents
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  X, Activity, Brain, BookOpen, Users, Search, Loader2,
  Database, Globe, Plus, Terminal, Check, GitBranch, Wrench, AlertCircle,
  Bot, File, Pencil, Code2, User,
} from "lucide-react";
import type { ContextTab, AgentActivity, MemoryEntry, KnowledgeEntity } from "@/types/nexus";

const TABS: { id: ContextTab; icon: React.ElementType; label: string }[] = [
  { id: "activity", icon: Activity, label: "Activite" },
  { id: "memory", icon: Brain, label: "Memoire" },
  { id: "knowledge", icon: BookOpen, label: "Savoir" },
  { id: "agents", icon: Users, label: "Agents" },
];

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  agent_thinking: <Loader2 size={11} className="animate-spin text-cyan-400" />,
  agent_action: <Bot size={11} className="text-teal-400" />,
  tool_call: <Terminal size={11} className="text-blue-400" />,
  tool_result: <Check size={11} className="text-emerald-400" />,
  file_create: <File size={11} className="text-emerald-400" />,
  file_edit: <Pencil size={11} className="text-amber-400" />,
  code_building: <Code2 size={11} className="text-purple-400" />,
  task_step: <GitBranch size={11} className="text-yellow-400" />,
  task_done: <Check size={11} className="text-emerald-500" />,
  error: <AlertCircle size={11} className="text-red-400" />,
};

export function ContextPanel() {
  const { contextOpen, closeContext, contextTab, setContextTab, agentActivity, agents } = useNexusStore();

  if (!contextOpen) return null;

  return (
    <motion.aside
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 320, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="h-full border-l border-border/20 bg-card/40 backdrop-blur-sm shrink-0 overflow-hidden flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-10 border-b border-border/20 shrink-0">
        <div className="flex items-center gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setContextTab(tab.id)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-colors ${
                contextTab === tab.id ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <tab.icon size={12} />
              <span className="hidden xl:inline">{tab.label}</span>
            </button>
          ))}
        </div>
        <button onClick={closeContext} className="text-muted-foreground hover:text-foreground p-1">
          <X size={14} />
        </button>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-3">
          {contextTab === "activity" && <ActivityTab activities={agentActivity} />}
          {contextTab === "memory" && <MemoryTab />}
          {contextTab === "knowledge" && <KnowledgeTab />}
          {contextTab === "agents" && <AgentsTab agents={agents} />}
        </div>
      </ScrollArea>
    </motion.aside>
  );
}

// ── Activity Tab ─────────────────────────────────────────────

function ActivityTab({ activities }: { activities: AgentActivity[] }) {
  if (activities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <Activity size={24} className="mb-2 opacity-30" />
        <p className="text-xs">Aucune activite en cours</p>
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {activities.slice(-30).reverse().map((a) => (
        <div key={a.id} className="flex items-start gap-2 py-1">
          <span className="shrink-0 mt-0.5">{ACTIVITY_ICONS[a.type] || <Wrench size={11} className="text-muted-foreground" />}</span>
          <span className="text-[11px] text-muted-foreground leading-relaxed break-all">
            {a.content.slice(0, 120)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Memory Tab ───────────────────────────────────────────────

function MemoryTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [searching, setSearching] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await nexusApi.searchMemory(query, "knowledge", 10);
      setResults(res);
    } catch { setResults([]); }
    finally { setSearching(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-1.5">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher dans la memoire..."
          className="h-8 text-xs"
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Button onClick={handleSearch} disabled={searching} size="sm" className="h-8 w-8 p-0">
          {searching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
        </Button>
      </div>

      {results.length > 0 && (
        <div className="space-y-1.5 max-h-80 overflow-y-auto">
          {results.map((r, i) => (
            <div key={i} className="p-2 rounded-md bg-muted/20 border border-border/15">
              <p className="text-[11px] line-clamp-3">{r.text}</p>
              <span className="text-[9px] text-muted-foreground mt-1 block">distance: {r.distance.toFixed(3)}</span>
            </div>
          ))}
        </div>
      )}

      {results.length === 0 && !searching && (
        <p className="text-[11px] text-muted-foreground text-center py-4">Recherchez dans la memoire vectorielle</p>
      )}
    </div>
  );
}

// ── Knowledge Tab ────────────────────────────────────────────

function KnowledgeTab() {
  const [query, setQuery] = useState("");
  const [entities, setEntities] = useState<KnowledgeEntity[]>([]);
  const [searching, setSearching] = useState(false);
  const [webQuery, setWebQuery] = useState("");
  const [webResults, setWebResults] = useState<{ title: string; url: string; snippet: string }[]>([]);
  const [webSearching, setWebSearching] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await nexusApi.knowledgeSearch(query);
      setEntities(res);
    } catch { setEntities([]); }
    finally { setSearching(false); }
  };

  const handleWebSearch = async () => {
    if (!webQuery.trim()) return;
    setWebSearching(true);
    try {
      const res = await nexusApi.webSearch(webQuery, 5);
      setWebResults(res.results);
    } catch { setWebResults([]); }
    finally { setWebSearching(false); }
  };

  return (
    <div className="space-y-3">
      {/* Knowledge Graph */}
      <div>
        <div className="flex gap-1.5 mb-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Graphe de connaissances..."
            className="h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <Button onClick={handleSearch} disabled={searching} size="sm" className="h-8 w-8 p-0">
            {searching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
          </Button>
        </div>
        {entities.length > 0 && (
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {entities.map((e, i) => (
              <div key={i} className="flex items-center gap-2 p-1.5 rounded bg-muted/15">
                <div className="w-1.5 h-1.5 rounded-full bg-primary/60" />
                <span className="text-[11px] truncate">{e.name}</span>
                <Badge variant="outline" className="text-[8px] h-4">{e.type}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Web Search */}
      <div>
        <div className="flex gap-1.5 mb-2">
          <Input
            value={webQuery}
            onChange={(e) => setWebQuery(e.target.value)}
            placeholder="Recherche web..."
            className="h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && handleWebSearch()}
          />
          <Button onClick={handleWebSearch} disabled={webSearching} size="sm" className="h-8 w-8 p-0">
            {webSearching ? <Loader2 size={12} className="animate-spin" /> : <Globe size={12} />}
          </Button>
        </div>
        {webResults.length > 0 && (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {webResults.map((r, i) => (
              <a key={i} href={r.url} target="_blank" rel="noopener noreferrer" className="block p-1.5 rounded bg-muted/15 hover:bg-muted/25 transition-colors">
                <p className="text-[11px] font-medium text-primary truncate">{r.title}</p>
                <p className="text-[10px] text-muted-foreground line-clamp-2">{r.snippet}</p>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Agents Tab ───────────────────────────────────────────────

function AgentsTab({ agents }: { agents: { id: string; name: string; type: string; status: string; task: string; progress: number }[] }) {
  const [taskInput, setTaskInput] = useState("");
  const [spawning, setSpawning] = useState(false);
  const { addAgent } = useNexusStore();

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
    } catch {} finally { setSpawning(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-1.5">
        <Input
          value={taskInput}
          onChange={(e) => setTaskInput(e.target.value)}
          placeholder="Nouvelle tache agent..."
          className="h-8 text-xs"
          onKeyDown={(e) => e.key === "Enter" && handleSpawn()}
        />
        <Button onClick={handleSpawn} disabled={spawning || !taskInput.trim()} size="sm" className="h-8 w-8 p-0">
          {spawning ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
        </Button>
      </div>

      {agents.length > 0 ? (
        <div className="space-y-1.5">
          {agents.map((agent) => (
            <div key={agent.id} className="p-2 rounded-md bg-muted/15 border border-border/15">
              <div className="flex items-center gap-2">
                <User size={12} className="text-primary shrink-0" />
                <span className="text-[11px] font-medium truncate">{agent.name}</span>
                <Badge variant={agent.status === "running" ? "default" : "secondary"} className="text-[8px] h-4 ml-auto">
                  {agent.status}
                </Badge>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{agent.task}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground text-center py-4">Aucun agent actif</p>
      )}
    </div>
  );
}
