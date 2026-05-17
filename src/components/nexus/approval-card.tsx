// ═══════════════════════════════════════════════════════════════
// NEXUS — Approval Card Component
// HITL (Human-In-The-Loop) approval request card
// ═══════════════════════════════════════════════════════════════

"use client";

import React, { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Shield } from "lucide-react";
import { nexusApi } from "@/lib/nexus-api";
import type { ApprovalRequest } from "@/types/nexus";

// ── Approval Card Props ─────────────────────────────────────

interface ApprovalCardProps {
  approvals: ApprovalRequest[];
  onRemove: (id: string) => void;
}

// ── Approval Card Component ─────────────────────────────────

export const ApprovalCard = React.memo(function ApprovalCard({
  approvals,
  onRemove,
}: ApprovalCardProps) {
  const handleApprove = useCallback(async (id: string) => {
    await nexusApi.approveAction(id);
    onRemove(id);
  }, [onRemove]);

  const handleDeny = useCallback(async (id: string) => {
    await nexusApi.denyAction(id);
    onRemove(id);
  }, [onRemove]);

  if (approvals.length === 0) return null;

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
      <div className="flex items-center gap-2 mb-2">
        <Shield size={12} className="text-amber-500" />
        <span className="text-[11px] font-medium text-amber-500">Approbation requise</span>
      </div>
      {approvals.slice(-3).map((req) => (
        <div key={req.id} className="flex items-center gap-2 p-2 rounded-lg bg-background/50 mb-1">
          <span className="text-[10px] text-foreground/80 flex-1">
            {req.toolName}: {JSON.stringify(req.args).slice(0, 80)}
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-5 text-[9px] text-emerald-500 hover:text-emerald-400"
              onClick={() => handleApprove(req.id)}
            >
              Autoriser
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-5 text-[9px] text-red-500 hover:text-red-400"
              onClick={() => handleDeny(req.id)}
            >
              Refuser
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
});
