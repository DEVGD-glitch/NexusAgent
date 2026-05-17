// ═══════════════════════════════════════════════════════════════
// NEXUS — Thinking Panel Component
// Shows agent reasoning in real-time during task execution
// ═══════════════════════════════════════════════════════════════

"use client";

import React from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import type { AgentActivity } from "@/types/nexus";

// ── Thinking Panel Props ────────────────────────────────────

interface ThinkingPanelProps {
  activities: AgentActivity[];
}

// ── Thinking Panel Component ────────────────────────────────

export const ThinkingPanel = React.memo(function ThinkingPanel({
  activities,
}: ThinkingPanelProps) {
  const thinkingActivities = activities.filter((a) => a.type === "agent_thinking");

  if (thinkingActivities.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3"
    >
      <div className="flex items-center gap-2 mb-2">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          <Loader2 size={12} className="text-cyan-500" />
        </motion.div>
        <span className="text-[11px] font-medium text-cyan-500">Reflexion en cours...</span>
      </div>
      <div className="space-y-1 max-h-32 overflow-y-auto">
        {thinkingActivities
          .slice(-5)
          .map((a) => (
            <p key={a.id} className="text-[10px] text-foreground/60 font-mono">
              {a.content}
            </p>
          ))}
      </div>
    </motion.div>
  );
});
