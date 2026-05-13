"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { useNexusStore, type AgentInstance, type AgentActivity } from "@/lib/nexus-store";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  Plus, CheckCircle2, XCircle, Circle, Clock, Activity,
  Brain, MessageSquare, Bot, Sparkles, Terminal, FileText,
  GitBranch, Trash2, Loader2,
} from "lucide-react";

/* ── Helpers ── */

function formatElapsed(startedAt: number, completedAt?: number): string {
  const diff = (completedAt ?? Date.now()) - startedAt;
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatTimestamp(ts: number): string {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 10) return "à l'instant";
  if (s < 60) return `il y a ${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `il y a ${m}m`;
  const h = Math.floor(m / 60);
  return `il y a ${h}h`;
}

const ACTIVITY_ICON: Record<string, typeof Brain> = {
  thought: Brain,
  tool_call: Terminal,
  tool_result: CheckCircle2,
  task_step: Activity,
  task_done: CheckCircle2,
  error: XCircle,
  file_create: FileText,
  file_edit: FileText,
  code_diff: GitBranch,
};

const ACTIVITY_COLOR: Record<string, string> = {
  thought: "text-purple-400",
  tool_call: "text-blue-400",
  tool_result: "text-emerald-400",
  task_step: "text-amber-400",
  task_done: "text-emerald-400",
  error: "text-red-400",
  file_create: "text-sky-400",
  file_edit: "text-sky-400",
  code_diff: "text-violet-400",
};

/* ── Sub-components ── */

function StatusDot({ status }: { status: AgentInstance["status"] }) {
  const styles: Record<string, string> = {
    running: "bg-emerald-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]",
    pending: "bg-muted-foreground/40",
    completed: "bg-blue-500",
    failed: "bg-red-500",
  };
  return (
    <motion.span
      animate={{ scale: [1, 1.3, 1] }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn("inline-block size-2 rounded-full shrink-0", styles[status])}
    />
  );
}

function ProgressBar({ value, status }: { value: number; status: AgentInstance["status"] }) {
  const fillStyles: Record<string, string> = {
    running: "bg-gradient-to-r from-cyan-500 to-cyan-400",
    pending: "bg-muted-foreground/30",
    completed: "bg-emerald-500",
    failed: "bg-red-500",
  };
  return (
    <div className="h-0.5 w-full rounded-full bg-muted overflow-hidden">
      <motion.div
        className={cn("h-full rounded-full", fillStyles[status])}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      />
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
      {count !== undefined && (
        <Badge variant="outline" className="text-[10px] h-4 px-1.5 leading-none">{count}</Badge>
      )}
    </div>
  );
}

/* ── Agent Card ── */

function AgentCard({ agent }: { agent: AgentInstance }) {
  const { setActiveAgent, removeAgent } = useNexusStore();
  const isRunning = agent.status === "running";

  function handleClick() {
    setActiveAgent(agent.id);
  }

  function handleRemove(e: React.MouseEvent) {
    e.stopPropagation();
    removeAgent(agent.id);
  }

  return (
    <Card
      size="sm"
      className={cn(
        "cursor-pointer transition-all duration-200 hover:border-cyan-500/30",
        "bg-card/90 backdrop-blur-[1px]",
        isRunning && "ring-1 ring-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.12)]",
      )}
      onClick={handleClick}
    >
      <CardContent className="space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <StatusDot status={agent.status} />
            <span className="text-sm font-medium truncate">{agent.name}</span>
          </div>
          <Badge variant="secondary" className="text-[10px] shrink-0 leading-none">
            {agent.type}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground truncate leading-relaxed">{agent.task}</p>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              {isRunning ? (
                <Loader2 size={10} className="animate-spin text-cyan-400" />
              ) : (
                <Clock size={10} />
              )}
              <span>{formatElapsed(agent.startedAt, agent.completedAt)}</span>
            </div>
            <span className={cn(
              "font-medium tabular-nums",
              isRunning && "text-cyan-400",
              agent.status === "completed" && "text-emerald-400",
              agent.status === "failed" && "text-red-400",
            )}>
              {agent.progress}%
            </span>
          </div>
          <ProgressBar value={agent.progress} status={agent.status} />
        </div>
        <div className="flex items-center justify-between pt-0.5">
          <span className="text-[10px] text-muted-foreground/60">
            {agent.activityCount} activité{agent.activityCount !== 1 ? "s" : ""}
          </span>
          <button
            onClick={handleRemove}
            className="text-muted-foreground/40 hover:text-red-400 transition-colors"
            title="Supprimer"
          >
            <Trash2 size={11} />
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ── Agent Section ── */

function AgentSection({ title, count, agents }: { title: string; count: number; agents: AgentInstance[] }) {
  if (agents.length === 0) return null;
  return (
    <section className="space-y-3">
      <SectionHeader title={title} count={count} />
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
        initial="hidden"
        animate="visible"
        variants={{
          visible: { transition: { staggerChildren: 0.06 } },
        }}
      >
        {agents.map((a) => (
          <motion.div
            key={a.id}
            variants={{
              hidden: { opacity: 0, y: 12 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: "easeOut" } },
            }}
          >
            <AgentCard agent={a} />
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

/* ── Activity Feed ── */

function ActivityFeedSection({ activities }: { activities: AgentActivity[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const recent = activities.slice(-10);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activities.length]);

  if (recent.length === 0) return null;

  return (
    <section className="space-y-3">
      <SectionHeader title="Fil d'activité" />
      <Card>
        <CardContent className="p-3 max-h-[220px] overflow-y-auto">
          {recent.map((a, i) => {
            const Icon = ACTIVITY_ICON[a.type] ?? Activity;
            const color = ACTIVITY_COLOR[a.type] ?? "text-muted-foreground";
            return (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2, ease: "easeOut", delay: i * 0.03 }}
                className="flex items-start gap-2.5 py-1.5 text-xs border-b border-border/30 last:border-0"
              >
                <Icon size={12} className={cn("shrink-0 mt-0.5", color)} />
                <span className="text-muted-foreground min-w-0 flex-1 truncate">
                  {a.content.replace(/\*\*/g, "").slice(0, 100)}
                </span>
                <span className="text-[10px] text-muted-foreground/40 shrink-0 whitespace-nowrap">
                  {formatTimestamp(a.timestamp)}
                </span>
              </motion.div>
            );
          })}
          <div ref={bottomRef} />
        </CardContent>
      </Card>
    </section>
  );
}

/* ── Empty State ── */

function EmptyState() {
  const { addConversation, setActivePanel } = useNexusStore();

  function handleNewChat() {
    addConversation();
    setActivePanel("chat");
  }

  function handleNewTask() {
    setActivePanel("tasks");
  }

  return (
    <div className="flex items-center justify-center min-h-[500px]">
      <Card className="w-full max-w-lg text-center">
        <CardContent className="p-10 space-y-6">
          <div className="flex justify-center">
            <div className="size-16 rounded-2xl bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
              <Bot size={32} className="text-primary" />
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="text-lg font-semibold">Bienvenue dans NEXUS</h2>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
              Centre de commande de vos agents IA. Commencez une conversation ou lancez une tâche automatisée.
            </p>
          </div>
          <div className="flex gap-3 justify-center">
            <Button onClick={handleNewChat} variant="default" className="gap-2 h-9">
              <MessageSquare size={14} />
              Nouveau Chat
            </Button>
            <Button onClick={handleNewTask} variant="secondary" className="gap-2 h-9">
              <Sparkles size={14} />
              Nouvelle Tâche
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground/50">
            Les agents en cours d'exécution apparaîtront ici avec leur progression en temps réel
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/* ── Loading Skeleton ── */

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2].map((s) => (
        <div key={s} className="space-y-3">
          <Skeleton className="h-4 w-28" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map((c) => (
              <Card key={c} size="sm">
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Skeleton className="size-2 rounded-full" />
                    <Skeleton className="h-4 flex-1" />
                    <Skeleton className="h-4 w-14" />
                  </div>
                  <Skeleton className="h-3 w-full" />
                  <div className="space-y-1.5">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-0.5 w-full" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main Component ── */

export function AgentsWallPanel() {
  const { agents, agentActivity } = useNexusStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(t);
  }, []);

  const running = agents.filter((a) => a.status === "running");
  const pending = agents.filter((a) => a.status === "pending");
  const completed = agents.filter((a) => a.status === "completed");
  const failed = agents.filter((a) => a.status === "failed");
  const hasAgents = agents.length > 0;

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <h1 className="text-sm font-semibold flex items-center gap-2">
          <Bot size={16} className="text-primary" />
          Agents Wall
        </h1>
        <div className="flex items-center gap-2">
          {hasAgents && (
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {agents.length} agent{agents.length !== 1 ? "s" : ""}
            </span>
          )}
          <Button variant="default" size="sm" className="h-7 gap-1 text-xs">
            <Plus size={14} />
            Nouvel agent
          </Button>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6 max-w-6xl mx-auto">
          {loading ? (
            <LoadingSkeleton />
          ) : hasAgents ? (
            <>
              <AgentSection title="En cours" count={running.length} agents={running} />
              <AgentSection title="En attente" count={pending.length} agents={pending} />
              <AgentSection title="Terminés" count={completed.length} agents={completed} />
              <AgentSection title="Échoués" count={failed.length} agents={failed} />
              <ActivityFeedSection activities={agentActivity} />
            </>
          ) : (
            <EmptyState />
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
