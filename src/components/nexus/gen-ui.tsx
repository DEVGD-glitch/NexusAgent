// ═══════════════════════════════════════════════════════════════
// NEXUS — Generative UI Components
// Rich interactive cards that render INSIDE chat messages
// The agent decides what to show — no separate panels needed
// ═══════════════════════════════════════════════════════════════

"use client";

import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Brain, Globe, File, Pencil, Terminal, Check, X,
  Code2, GitBranch, Package, Wrench, Loader2,
  Search, Database, ExternalLink, Copy, Play,
} from "lucide-react";
import type { BuildStep } from "@/types/nexus";

// ── Base Card Wrapper ───────────────────────────────────────

function GenCard({ children, icon, title, className = "" }: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2 }}
      className={`rounded-xl border border-border/20 bg-muted/10 overflow-hidden ${className}`}
    >
      {(icon || title) && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border/10 bg-muted/5">
          {icon}
          {title && <span className="text-[11px] font-medium text-foreground/70">{title}</span>}
        </div>
      )}
      <div className="p-3">{children}</div>
    </motion.div>
  );
}

// ── Memory Result Card ──────────────────────────────────────
// Shown when agent searches memory — results in chat

export function MemoryCard({ results }: {
  results: { text: string; source: string; distance: number }[];
}) {
  return (
    <GenCard
      icon={<Brain size={12} className="text-violet-400" />}
      title="Memoire"
    >
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {results.map((r, i) => (
          <div key={i} className="p-2 rounded-lg bg-muted/15 border border-border/10">
            <p className="text-[11px] line-clamp-3 text-foreground/80">{r.text}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="text-[8px] h-4">{r.source}</Badge>
              <span className="text-[9px] text-muted-foreground">sim: {(1 - r.distance).toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
    </GenCard>
  );
}

// ── Web Search Result Card ──────────────────────────────────
// Shown when agent does web search — results in chat

export function WebResultCard({ results }: {
  results: { title: string; url: string; snippet: string }[];
}) {
  return (
    <GenCard
      icon={<Globe size={12} className="text-blue-400" />}
      title="Recherche web"
    >
      <div className="space-y-1.5 max-h-56 overflow-y-auto">
        {results.map((r, i) => (
          <a
            key={i}
            href={r.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-2 p-2 rounded-lg bg-muted/10 hover:bg-muted/20 transition-colors group"
          >
            <ExternalLink size={10} className="text-muted-foreground mt-1 shrink-0 group-hover:text-primary" />
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-primary truncate group-hover:underline">{r.title}</p>
              <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{r.snippet}</p>
            </div>
          </a>
        ))}
      </div>
    </GenCard>
  );
}

// ── Code Result Card ────────────────────────────────────────
// Shown when agent executes code — result in chat

export function CodeResultCard({ stdout, stderr, exitCode, timeMs }: {
  stdout: string;
  stderr: string;
  exitCode: number;
  timeMs: number;
}) {
  return (
    <GenCard
      icon={<Terminal size={12} className={exitCode === 0 ? "text-emerald-400" : "text-red-400"} />}
      title="Execution"
    >
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant={exitCode === 0 ? "default" : "destructive"} className="text-[8px]">
            Exit {exitCode}
          </Badge>
          <span className="text-[9px] text-muted-foreground">{timeMs}ms</span>
        </div>
        {stdout && (
          <pre className="text-[11px] font-mono text-emerald-400 bg-emerald-500/5 p-2 rounded-lg border border-emerald-500/10 whitespace-pre-wrap max-h-32 overflow-y-auto">{stdout}</pre>
        )}
        {stderr && (
          <pre className="text-[11px] font-mono text-red-400 bg-red-500/5 p-2 rounded-lg border border-red-500/10 whitespace-pre-wrap max-h-32 overflow-y-auto">{stderr}</pre>
        )}
      </div>
    </GenCard>
  );
}

// ── Build Steps Card ────────────────────────────────────────
// Shown when agent builds something — progress in chat

export function BuildStepsCard({ steps }: { steps: BuildStep[] }) {
  const completed = steps.filter(s => s.status === "completed").length;

  const ICON_MAP: Record<string, React.ReactNode> = {
    file_create: <File size={11} />,
    file_edit: <Pencil size={11} />,
    code_line: <Code2 size={11} />,
    dependency: <Package size={11} />,
    config: <Wrench size={11} />,
    test: <Check size={11} />,
    deploy: <GitBranch size={11} />,
  };

  return (
    <GenCard
      icon={<Code2 size={12} className="text-amber-400" />}
      title={`Construction (${completed}/${steps.length})`}
    >
      <div className="space-y-1 max-h-40 overflow-y-auto">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted/15">
            <span className={`shrink-0 ${
              step.status === "completed" ? "text-emerald-500" :
              step.status === "building" ? "text-amber-500 animate-pulse" :
              step.status === "error" ? "text-red-500" : "text-muted-foreground"
            }`}>
              {ICON_MAP[step.type] || <Wrench size={11} />}
            </span>
            <span className="text-[10px] text-foreground/70 truncate flex-1">{step.label}</span>
            {step.status === "completed" && <Check size={9} className="text-emerald-500 shrink-0" />}
            {step.status === "building" && <Loader2 size={9} className="text-amber-500 animate-spin shrink-0" />}
            {step.status === "error" && <X size={9} className="text-red-500 shrink-0" />}
          </div>
        ))}
      </div>
    </GenCard>
  );
}

// ── Agent Activity Card ─────────────────────────────────────
// Shown when agent is working — live activity in chat

export function AgentActivityCard({ activities }: {
  activities: { type: string; content: string }[];
}) {
  const ICON_MAP: Record<string, React.ReactNode> = {
    agent_thinking: <Loader2 size={10} className="animate-spin text-cyan-400" />,
    agent_action: <Wrench size={10} className="text-teal-400" />,
    tool_call: <Terminal size={10} className="text-blue-400" />,
    tool_result: <Check size={10} className="text-emerald-400" />,
    task_step: <GitBranch size={10} className="text-yellow-400" />,
    task_done: <Check size={10} className="text-emerald-500" />,
    error: <X size={10} className="text-red-400" />,
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3"
    >
      <div className="flex items-center gap-2 mb-2">
        <Loader2 size={10} className="animate-spin text-primary" />
        <span className="text-[10px] font-medium text-primary">NEXUS travaille...</span>
      </div>
      <div className="space-y-0.5 max-h-32 overflow-y-auto">
        {activities.slice(-6).map((a, i) => (
          <div key={i} className="flex items-start gap-1.5 py-0.5">
            <span className="shrink-0 mt-0.5">{ICON_MAP[a.type] || <Wrench size={10} className="text-muted-foreground" />}</span>
            <span className="text-[10px] text-muted-foreground leading-relaxed break-all">
              {a.content.slice(0, 100)}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ── Knowledge Entity Card ───────────────────────────────────
// Shown when agent queries knowledge graph — in chat

export function KnowledgeCard({ entities }: {
  entities: { name: string; type: string; properties?: Record<string, unknown> }[];
}) {
  return (
    <GenCard
      icon={<Database size={12} className="text-teal-400" />}
      title="Connaissances"
    >
      <div className="flex flex-wrap gap-1.5">
        {entities.map((e, i) => (
          <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/15 border border-border/10">
            <div className="w-1.5 h-1.5 rounded-full bg-teal-500/60" />
            <span className="text-[10px] font-medium">{e.name}</span>
            <Badge variant="outline" className="text-[7px] h-3.5 px-1">{e.type}</Badge>
          </div>
        ))}
      </div>
    </GenCard>
  );
}
