// ═══════════════════════════════════════════════════════════════
// NEXUS — Dashboard Monitoring
// Real-time system metrics: CPU, RAM, tokens, agents, errors
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Activity,
  Cpu,
  MemoryStick,
  Coins,
  Wrench,
  AlertTriangle,
  Users,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────

interface SystemMetrics {
  cpu_percent: number;
  memory_mb: number;
  tokens_used_today: number;
  tool_calls_today: number;
  errors_last_hour: number;
  agents_running: AgentInfo[];
  uptime_seconds: number;
}

interface AgentInfo {
  id: string;
  type: string;
  status: "running" | "idle" | "error" | "completed";
  task: string;
  tokens: number;
}

interface MetricHistory {
  timestamp: number;
  cpu: number;
  memory: number;
  tokens: number;
}

interface DashboardProps {
  open: boolean;
  onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────────

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatBytes(mb: number): string {
  if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(0)} MB`;
}

const STATUS_COLORS: Record<string, string> = {
  running: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  idle: "bg-muted/20 text-muted-foreground border-border/10",
  error: "bg-red-500/10 text-red-400 border-red-500/20",
  completed: "bg-blue-500/10 text-blue-400 border-blue-500/20",
};

// ── Metric Card ────────────────────────────────────────────────

function MetricCard({
  icon,
  label,
  value,
  unit,
  trend,
  color = "text-foreground",
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "flat";
  color?: string;
}) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="rounded-xl border border-border/20 bg-muted/5 p-3"
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          {icon}
          <span className="text-[10px] text-muted-foreground">{label}</span>
        </div>
        {trend && (
          <TrendIcon
            size={10}
            className={
              trend === "up"
                ? "text-emerald-500"
                : trend === "down"
                  ? "text-red-400"
                  : "text-muted-foreground"
            }
          />
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-lg font-bold ${color}`}>{value}</span>
        {unit && (
          <span className="text-[10px] text-muted-foreground">{unit}</span>
        )}
      </div>
    </motion.div>
  );
}

// ── Mini Sparkline ─────────────────────────────────────────────

function Sparkline({
  data,
  color = "#10b981",
  height = 24,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = height - (v / max) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 100 ${height}`}
      className="w-full"
      preserveAspectRatio="none"
      style={{ height }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

// ── Dashboard Component ────────────────────────────────────────

export function Dashboard({ open, onClose }: DashboardProps) {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [history, setHistory] = useState<MetricHistory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch("/api/metrics/dashboard");
      if (!res.ok) throw new Error(`${res.status}`);
      const data: SystemMetrics = await res.json();
      setMetrics(data);
      setHistory((prev) => {
        const next = [
          ...prev,
          {
            timestamp: Date.now(),
            cpu: data.cpu_percent,
            memory: data.memory_mb,
            tokens: data.tokens_used_today,
          },
        ];
        return next.slice(-60);
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    fetchMetrics();
    intervalRef.current = setInterval(fetchMetrics, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [open, fetchMetrics]);

  const cpuHistory = history.map((h) => h.cpu);
  const memHistory = history.map((h) => h.memory);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Activity size={16} className="text-emerald-500" />
            Dashboard
            <Badge variant="outline" className="text-[9px] ml-auto">
              {metrics ? `Uptime: ${formatUptime(metrics.uptime_seconds)}` : "—"}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-2 text-[11px] text-red-400">
            {error}
          </div>
        )}

        <div className="grid grid-cols-3 gap-2" role="status" aria-live="polite">
          <MetricCard
            icon={<Cpu size={12} className="text-blue-400" />}
            label="CPU"
            value={metrics?.cpu_percent.toFixed(1) ?? "—"}
            unit="%"
            color={
              (metrics?.cpu_percent ?? 0) > 80
                ? "text-red-400"
                : (metrics?.cpu_percent ?? 0) > 50
                  ? "text-yellow-400"
                  : "text-emerald-400"
            }
          />
          <MetricCard
            icon={<MemoryStick size={12} className="text-violet-400" />}
            label="Memory"
            value={metrics ? formatBytes(metrics.memory_mb) : "—"}
          />
          <MetricCard
            icon={<Coins size={12} className="text-amber-400" />}
            label="Tokens Today"
            value={
              metrics?.tokens_used_today?.toLocaleString() ?? "—"
            }
          />
          <MetricCard
            icon={<Wrench size={12} className="text-cyan-400" />}
            label="Tool Calls"
            value={metrics?.tool_calls_today?.toLocaleString() ?? "—"}
          />
          <MetricCard
            icon={<AlertTriangle size={12} className="text-red-400" />}
            label="Errors (1h)"
            value={metrics?.errors_last_hour ?? "—"}
            color={
              (metrics?.errors_last_hour ?? 0) > 0
                ? "text-red-400"
                : "text-emerald-400"
            }
          />
          <MetricCard
            icon={<Users size={12} className="text-emerald-400" />}
            label="Active Agents"
            value={metrics?.agents_running?.length ?? 0}
          />
        </div>

        {/* Sparklines */}
        {history.length > 5 && (
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-border/10 bg-muted/5 p-2">
              <span className="text-[9px] text-muted-foreground">
                CPU History
              </span>
              <Sparkline data={cpuHistory} color="#3b82f6" />
            </div>
            <div className="rounded-lg border border-border/10 bg-muted/5 p-2">
              <span className="text-[9px] text-muted-foreground">
                Memory History
              </span>
              <Sparkline data={memHistory} color="#8b5cf6" />
            </div>
          </div>
        )}

        {/* Active Agents */}
        <div className="rounded-lg border border-border/10">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border/10">
            <span className="text-[11px] font-medium">Active Agents</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 px-1.5"
              onClick={fetchMetrics}
              aria-label="Actualiser les metriques"
            >
              <RefreshCw size={10} />
            </Button>
          </div>
          <ScrollArea className="max-h-32">
            {metrics?.agents_running?.length ? (
              <div className="divide-y divide-border/5">
                {metrics.agents_running.map((agent) => (
                  <div
                    key={agent.id}
                    className="flex items-center gap-2 px-3 py-1.5"
                  >
                    <span className="text-[10px] font-mono text-muted-foreground w-16 truncate">
                      {agent.id.slice(0, 8)}
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[8px] h-4 ${STATUS_COLORS[agent.status]}`}
                    >
                      {agent.status}
                    </Badge>
                    <span className="text-[10px] text-foreground/70 flex-1 truncate">
                      {agent.task || agent.type}
                    </span>
                    <span className="text-[9px] text-muted-foreground">
                      {agent.tokens?.toLocaleString() ?? 0} tok
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground p-3 text-center">
                No active agents
              </p>
            )}
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
