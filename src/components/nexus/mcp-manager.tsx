// ═══════════════════════════════════════════════════════════════
// NEXUS — MCP Manager
// Install, enable/disable, and manage MCP servers
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Server,
  Plus,
  Search,
  AlertCircle,
  Loader2,
  ExternalLink,
  Coins,
  Shield,
  Trash2,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────

export interface MCPInfo {
  id: string;
  name: string;
  status: "enabled" | "disabled" | "error" | "installed";
  trust_level: "unknown" | "low" | "medium" | "high" | "verified";
  token_cost_estimate: number;
  permissions: string[];
  tags: string[];
  install_source: string;
}

interface MCPManagerProps {
  open: boolean;
  onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────────

const STATUS_CONFIG = {
  enabled: {
    dot: "bg-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    label: "Active",
  },
  disabled: {
    dot: "bg-muted-foreground/40",
    badge: "bg-muted/20 text-muted-foreground border-border/10",
    label: "Inactive",
  },
  error: {
    dot: "bg-red-500",
    badge: "bg-red-500/10 text-red-400 border-red-500/20",
    label: "Erreur",
  },
  installed: {
    dot: "bg-blue-500",
    badge: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    label: "Installe",
  },
} as const;

const TRUST_COLORS: Record<string, string> = {
  verified: "text-emerald-500",
  high: "text-blue-400",
  medium: "text-amber-400",
  low: "text-orange-400",
  unknown: "text-muted-foreground",
};

// ── Component ──────────────────────────────────────────────────

export function MCPManager({ open, onClose }: MCPManagerProps) {
  const [mcps, setMcps] = useState<MCPInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [installOpen, setInstallOpen] = useState(false);
  const [installUrl, setInstallUrl] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);

  const fetchMCPs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/mcp");
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setMcps(data.mcps ?? data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load MCPs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchMCPs();
  }, [open, fetchMCPs]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return mcps.filter(
      (m) =>
        !q ||
        m.name.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        m.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [mcps, search]);

  const handleToggle = useCallback(
    async (mcp: MCPInfo) => {
      const newStatus = mcp.status === "enabled" ? "disabled" : "enabled";
      setTogglingIds((prev) => new Set(prev).add(mcp.id));
      try {
        const res = await fetch(`/api/mcp/${mcp.id}/toggle`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
        if (!res.ok) throw new Error(`${res.status}`);
        setMcps((prev) =>
          prev.map((m) =>
            m.id === mcp.id ? { ...m, status: newStatus as MCPInfo["status"] } : m
          )
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Toggle failed");
      } finally {
        setTogglingIds((prev) => {
          const next = new Set(prev);
          next.delete(mcp.id);
          return next;
        });
      }
    },
    []
  );

  const handleInstall = useCallback(async () => {
    if (!installUrl.trim()) return;
    setInstalling(true);
    setInstallError(null);
    try {
      const res = await fetch("/api/mcp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: installUrl }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setInstallUrl("");
      setInstallOpen(false);
      await fetchMCPs();
    } catch (e) {
      setInstallError(e instanceof Error ? e.message : "Install failed");
    } finally {
      setInstalling(false);
    }
  }, [installUrl, fetchMCPs]);

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleDelete = useCallback(
    async (mcpId: string) => {
      if (deleteConfirmId !== mcpId) {
        setDeleteConfirmId(mcpId);
        return;
      }
      setDeleteConfirmId(null);
      try {
        const res = await fetch(`/api/mcp/${mcpId}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`${res.status}`);
        setMcps((prev) => prev.filter((m) => m.id !== mcpId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Delete failed");
      }
    },
    [deleteConfirmId]
  );

  const totalTokens = mcps
    .filter((m) => m.status === "enabled")
    .reduce((sum, m) => sum + m.token_cost_estimate, 0);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Server size={16} className="text-blue-400" />
            MCP Manager
            <Badge variant="outline" className="text-[9px] ml-auto">
              <Coins size={9} className="mr-1" />
              {totalTokens.toLocaleString()} tok/day
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Manage MCP servers — install, enable/disable, configure
          </DialogDescription>
        </DialogHeader>

        {/* Search + Install */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search
              size={12}
              className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              placeholder="Search MCPs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-7 h-7 text-[11px]"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-[10px] gap-1"
            onClick={() => setInstallOpen(true)}
          >
            <Plus size={10} />
            Install
          </Button>
        </div>

        {error && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-500/10 border border-red-500/20 p-2 text-[10px] text-red-400">
            <AlertCircle size={10} />
            {error}
          </div>
        )}

        {/* MCP List */}
        <ScrollArea className="flex-1 max-h-[50vh]">
          {loading ? (
            <div className="flex items-center justify-center py-8" role="status" aria-live="polite">
              <Loader2 size={16} className="animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-[11px] text-muted-foreground text-center py-6">
              {search ? "No MCPs match your search" : "No MCPs installed"}
            </p>
          ) : (
            <div className="space-y-1">
              <AnimatePresence>
                {filtered.map((mcp) => {
                  const config = STATUS_CONFIG[mcp.status];
                  const isToggling = togglingIds.has(mcp.id);
                  return (
                    <motion.div
                      key={mcp.id}
                      layout
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="flex items-center gap-3 rounded-lg border border-border/10 bg-muted/5 p-2.5"
                    >
                      {/* Status dot */}
                      <div
                        className={`w-1.5 h-1.5 rounded-full ${config.dot} shrink-0`}
                      />

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] font-medium truncate">
                            {mcp.name}
                          </span>
                          <Badge
                            variant="outline"
                            className={`text-[7px] h-3.5 px-1 ${config.badge}`}
                          >
                            {config.label}
                          </Badge>
                          <Shield
                            size={9}
                            className={TRUST_COLORS[mcp.trust_level]}
                          />
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[9px] text-muted-foreground">
                            {mcp.id}
                          </span>
                          {mcp.token_cost_estimate > 0 && (
                            <span className="text-[9px] text-amber-400">
                              ~{mcp.token_cost_estimate.toLocaleString()} tok
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        {isToggling ? (
                          <Loader2
                            size={12}
                            className="animate-spin text-muted-foreground"
                          />
                        ) : (
                          <Switch
                            checked={mcp.status === "enabled"}
                            onCheckedChange={() => handleToggle(mcp)}
                            className="scale-75"
                          />
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-5 w-5 p-0 text-muted-foreground hover:text-red-400"
                          onClick={() => handleDelete(mcp.id)}
                          aria-label={`Supprimer ${mcp.name}`}
                        >
                          <Trash2 size={10} />
                        </Button>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </ScrollArea>

        {/* Install Dialog */}
        <AnimatePresence>
          {installOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="rounded-lg border border-border/20 bg-muted/10 p-3 space-y-2"
            >
              <span className="text-[11px] font-medium">Install MCP</span>
              <div className="flex gap-2">
                <Input
                  placeholder="github.com/user/mcp-server"
                  value={installUrl}
                  onChange={(e) => setInstallUrl(e.target.value)}
                  className="h-7 text-[11px] flex-1"
                />
                <Button
                  size="sm"
                  className="h-7 text-[10px]"
                  onClick={handleInstall}
                  disabled={installing}
                >
                  {installing ? (
                    <Loader2 size={10} className="animate-spin" />
                  ) : (
                    "Install"
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-[10px]"
                  onClick={() => {
                    setInstallOpen(false);
                    setInstallError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
              {installError && (
                <p className="text-[10px] text-red-400">{installError}</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}
