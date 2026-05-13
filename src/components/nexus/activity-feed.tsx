// ═══════════════════════════════════════════════════════════════
// NEXUS — Activity Feed (inline in chat, compact)
// ═══════════════════════════════════════════════════════════════

"use client";

import { motion } from "framer-motion";
import { Loader2, Bot, Terminal, Check, File, Pencil, Code2, GitBranch, Wrench, AlertCircle } from "lucide-react";
import type { AgentActivity } from "@/types/nexus";

const ICON_MAP: Record<string, React.ReactNode> = {
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

export function ActivityFeed({ activities }: { activities: AgentActivity[] }) {
  return (
    <div className="rounded-xl border border-border/20 bg-muted/15 p-3 space-y-0.5">
      <div className="flex items-center gap-2 mb-1.5 text-[11px] font-medium text-foreground/60">
        <Loader2 size={11} className="animate-spin text-primary" />
        <span>NEXUS travaille...</span>
      </div>
      {activities.map((a) => (
        <motion.div
          key={a.id}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.12 }}
          className="flex items-start gap-1.5 py-0.5"
        >
          <span className="shrink-0 mt-0.5">{ICON_MAP[a.type] || <Wrench size={11} className="text-muted-foreground" />}</span>
          <span className="text-[11px] text-muted-foreground leading-relaxed break-all">
            {a.content.slice(0, 150)}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
