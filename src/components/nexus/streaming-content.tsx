// ═══════════════════════════════════════════════════════════════
// NEXUS — Streaming Content Component
// Displays streaming assistant response with cursor animation
// ═══════════════════════════════════════════════════════════════

"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Zap } from "lucide-react";

// ── Streaming Content Props ─────────────────────────────────

interface StreamingContentProps {
  content: string;
}

// ── Streaming Content Component ─────────────────────────────

export const StreamingContent = React.memo(function StreamingContent({
  content,
}: StreamingContentProps) {
  if (!content) return null;

  return (
    <div className="flex gap-3">
      <div className="shrink-0 mt-1 w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center">
        <Zap size={12} className="text-white" />
      </div>
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed bg-muted/40 border border-border/15">
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
        <span className="inline-block w-1.5 h-4 bg-primary/70 animate-pulse rounded-sm ml-0.5" />
      </div>
    </div>
  );
});
