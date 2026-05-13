// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Agent Avatar (SVG with expressions + animation)
// ═══════════════════════════════════════════════════════════════

"use client";

import { motion } from "framer-motion";
import type { AvatarExpression } from "@/types/nexus";

interface AvatarProps {
  expression: AvatarExpression;
  thinking: boolean;
  size?: number;
  className?: string;
  inline?: boolean;
}

const MOUTH_PATHS: Record<string, string> = {
  neutral: "M38 62 Q50 66 62 62",
  joy: "M36 60 Q50 72 64 60",
  thinking: "M38 62 Q50 64 62 62",
  surprise: "M42 60 Q50 68 58 60",
  relaxed: "M38 63 Q50 65 62 63",
  sad: "M38 64 Q50 60 62 64",
  angry: "M38 61 L42 65 L50 61 L58 65 L62 61",
};

export function NexusAvatar({ expression, thinking, size = 48, className = "", inline = false }: AvatarProps) {
  const mouthD = MOUTH_PATHS[expression] || MOUTH_PATHS.neutral;
  const eyeY = expression === "joy" ? 40 : 42;

  return (
    <motion.div
      className={`relative ${className}`}
      animate={thinking ? { scale: [1, 1.03, 1] } : { scale: 1 }}
      transition={thinking ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : {}}
    >
      <svg viewBox="0 0 100 100" width={size} height={size} className="drop-shadow-lg">
        <defs>
          <radialGradient id={`av-grad-${inline ? "i" : "s"}`} cx="50%" cy="35%" r="55%">
            <stop offset="0%" stopColor="#5eead4" />
            <stop offset="50%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#0e7490" />
          </radialGradient>
          <radialGradient id={`av-glow-${inline ? "i" : "s"}`} cx="50%" cy="50%" r="50%">
            <stop offset="60%" stopColor="rgba(6,182,212,0.12)" />
            <stop offset="100%" stopColor="rgba(6,182,212,0)" />
          </radialGradient>
        </defs>

        {/* Outer glow */}
        <circle cx="50" cy="50" r="52" fill={`url(#av-glow-${inline ? "i" : "s"})`} />

        {/* Main face */}
        <circle cx="50" cy="50" r="45" fill={`url(#av-grad-${inline ? "i" : "s"})`} opacity={thinking ? 0.7 : 0.9} />
        <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />

        {/* Thinking animation rings */}
        {thinking && (
          <>
            <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(94,234,212,0.3)" strokeWidth="1.5" strokeDasharray="6 4">
              <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="4s" repeatCount="indefinite" />
            </circle>
            <circle cx="50" cy="50" r="51" fill="none" stroke="rgba(6,182,212,0.15)" strokeWidth="1" strokeDasharray="3 6">
              <animateTransform attributeName="transform" type="rotate" from="360 50 50" to="0 50 50" dur="3s" repeatCount="indefinite" />
            </circle>
          </>
        )}

        {/* Eyes */}
        <g fill="white">
          <ellipse cx="33" cy={eyeY} rx="5.5" ry="6" />
          <ellipse cx="67" cy={eyeY} rx="5.5" ry="6" />
          <ellipse cx="34.5" cy={eyeY + 0.5} rx="2.5" ry="3" fill="#0f172a" />
          <ellipse cx="68.5" cy={eyeY + 0.5} rx="2.5" ry="3" fill="#0f172a" />
          <circle cx="36" cy={eyeY - 1} r="1" fill="rgba(255,255,255,0.6)" />
          <circle cx="70" cy={eyeY - 1} r="1" fill="rgba(255,255,255,0.6)" />
        </g>

        {/* Mouth */}
        {expression === "joy" ? (
          <path d={mouthD} stroke="white" strokeWidth="2.8" fill="none" strokeLinecap="round" />
        ) : (
          <path d={mouthD} stroke="white" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        )}
      </svg>

      {/* Status dot */}
      <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-background ${
        thinking ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]" : "bg-muted-foreground/40"
      }`} />
    </motion.div>
  );
}
