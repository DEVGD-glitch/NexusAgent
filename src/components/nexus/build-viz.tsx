// ═══════════════════════════════════════════════════════════════
// NEXUS — Build Visualization (Brick-by-Brick, shown in chat)
// ═══════════════════════════════════════════════════════════════

"use client";

import { motion } from "framer-motion";
import { File, Pencil, Code2, Package, Wrench, Check, GitBranch, X } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import type { BuildStep } from "@/types/nexus";

const ICON_MAP: Record<string, React.ReactNode> = {
  file_create: <File size={13} />,
  file_edit: <Pencil size={13} />,
  code_line: <Code2 size={13} />,
  dependency: <Package size={13} />,
  config: <Wrench size={13} />,
  test: <Check size={13} />,
  deploy: <GitBranch size={13} />,
};

export function BuildVisualization({ steps }: { steps: BuildStep[] }) {
  if (steps.length === 0) return null;

  return (
    <div className="rounded-xl border border-border/20 bg-muted/15 p-3 space-y-1.5">
      <div className="flex items-center gap-2 text-[11px] font-medium text-foreground/70">
        <Code2 size={13} className="text-primary" />
        <span>Construction</span>
        <span className="text-muted-foreground">({steps.filter(s => s.status === "completed").length}/{steps.length})</span>
      </div>
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {steps.map((step, i) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.12, delay: i * 0.02 }}
            className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted/25"
          >
            <span className={`shrink-0 ${
              step.status === "completed" ? "text-emerald-500" :
              step.status === "building" ? "text-amber-500 animate-pulse" :
              step.status === "error" ? "text-red-500" : "text-muted-foreground"
            }`}>
              {ICON_MAP[step.type] || <Wrench size={13} />}
            </span>
            <span className="text-[11px] text-foreground/70 truncate flex-1">{step.label}</span>
            {step.status === "building" && step.progress > 0 && (
              <Progress value={step.progress} className="w-12 h-0.5" />
            )}
            {step.status === "completed" && <Check size={10} className="text-emerald-500 shrink-0" />}
            {step.status === "error" && <X size={10} className="text-red-500 shrink-0" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
