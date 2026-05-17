// ═══════════════════════════════════════════════════════════════
// NEXUS — Permission Manager
// Per-agent permission configuration UI
// ═══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Shield,
  FileText,
  Globe,
  Terminal,
  Monitor,
  Clipboard,
  Mic,
  Loader2,
  AlertCircle,
  Check,
  X,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────

interface Permission {
  id: string;
  name: string;
  icon: React.ReactNode;
  category: string;
  allowed: boolean;
  scope: "full" | "limited" | "none";
  details?: string;
}

interface AgentPermissionProfile {
  agent_id: string;
  agent_type: string;
  permissions: Permission[];
}

interface PermissionManagerProps {
  open: boolean;
  onClose: () => void;
  agentId?: string;
}

// ── Category Icons ─────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  filesystem: <FileText size={12} className="text-blue-400" />,
  network: <Globe size={12} className="text-emerald-400" />,
  shell: <Terminal size={12} className="text-amber-400" />,
  browser: <Monitor size={12} className="text-violet-400" />,
  clipboard: <Clipboard size={12} className="text-cyan-400" />,
  microphone: <Mic size={12} className="text-pink-400" />,
};

const SCOPE_COLORS: Record<string, string> = {
  full: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  limited: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  none: "bg-red-500/10 text-red-400 border-red-500/20",
};

// ── Component ──────────────────────────────────────────────────

export function PermissionManager({
  open,
  onClose,
  agentId,
}: PermissionManagerProps) {
  const [profile, setProfile] = useState<AgentPermissionProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<{ id: string; type: string }[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>(
    agentId
  );
  const [saving, setSaving] = useState(false);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch("/api/agents");
      if (!res.ok) return;
      const data = await res.json();
      setAgents(data.agents ?? []);
    } catch {
      // silent
    }
  }, []);

  const fetchPermissions = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/agents/${id}/permissions`);
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setProfile(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchAgents();
      if (selectedAgent) fetchPermissions(selectedAgent);
    }
  }, [open, selectedAgent, fetchAgents, fetchPermissions]);

  const handleToggle = useCallback(
    async (permId: string, allowed: boolean) => {
      if (!profile) return;
      setSaving(true);
      try {
        const res = await fetch(
          `/api/agents/${profile.agent_id}/permissions/${permId}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ allowed }),
          }
        );
        if (!res.ok) throw new Error(`${res.status}`);
        setProfile((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            permissions: prev.permissions.map((p) =>
              p.id === permId
                ? { ...p, allowed, scope: allowed ? "full" : "none" }
                : p
            ),
          };
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Update failed");
      } finally {
        setSaving(false);
      }
    },
    [profile]
  );

  const handleBatchToggle = useCallback(
    async (allowed: boolean) => {
      if (!profile) return;
      setSaving(true);
      try {
        const updates = profile.permissions
          .filter((p) => p.allowed !== allowed)
          .map((p) => ({ id: p.id, allowed }));
        if (updates.length === 0) return;
        // Single batch API call
        const res = await fetch(
          `/api/agents/${profile.agent_id}/permissions`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ permissions: updates }),
          }
        );
        if (!res.ok) throw new Error(`${res.status}`);
        setProfile((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            permissions: prev.permissions.map((p) => ({
              ...p,
              allowed,
              scope: allowed ? "full" : "none",
            })),
          };
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Batch update failed");
      } finally {
        setSaving(false);
      }
    },
    [profile]
  );

  const grouped = useMemo(
    () =>
      profile?.permissions.reduce(
        (acc, perm) => {
          const cat = perm.category;
          if (!acc[cat]) acc[cat] = [];
          acc[cat].push(perm);
          return acc;
        },
        {} as Record<string, Permission[]>
      ),
    [profile?.permissions]
  );

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield size={16} className="text-violet-400" />
            Permissions
            {profile && (
              <Badge variant="outline" className="text-[9px] ml-auto">
                {profile.agent_type}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Configure per-agent permissions for filesystem, network, shell, and
            more
          </DialogDescription>
        </DialogHeader>

        {/* Agent Selector */}
        {agents.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {agents.map((agent) => (
              <Button
                key={agent.id}
                variant={
                  selectedAgent === agent.id ? "default" : "outline"
                }
                size="sm"
                className="h-6 text-[9px] gap-1"
                onClick={() => setSelectedAgent(agent.id)}
              >
                {agent.id.slice(0, 8)}
                <span className="text-muted-foreground">{agent.type}</span>
              </Button>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-500/10 border border-red-500/20 p-2 text-[10px] text-red-400">
            <AlertCircle size={10} />
            {error}
          </div>
        )}

        {/* Permissions */}
        <ScrollArea className="flex-1 max-h-[50vh]">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2
                size={16}
                className="animate-spin text-muted-foreground"
              />
            </div>
          ) : !selectedAgent ? (
            <p className="text-[11px] text-muted-foreground text-center py-6">
              Select an agent to view permissions
            </p>
          ) : !grouped || Object.keys(grouped).length === 0 ? (
            <p className="text-[11px] text-muted-foreground text-center py-6">
              No permissions configured
            </p>
          ) : (
            <div className="space-y-3">
              {Object.entries(grouped).map(([category, perms]) => (
                <motion.div
                  key={category}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="rounded-lg border border-border/10 overflow-hidden"
                >
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/5 border-b border-border/10">
                    {CATEGORY_ICONS[category] || (
                      <Shield size={12} className="text-muted-foreground" />
                    )}
                    <span className="text-[10px] font-medium capitalize">
                      {category}
                    </span>
                    <span className="text-[8px] text-muted-foreground ml-auto">
                      {perms.filter((p) => p.allowed).length}/{perms.length}{" "}
                      allowed
                    </span>
                  </div>
                  <div className="divide-y divide-border/5">
                    {perms.map((perm) => (
                      <div
                        key={perm.id}
                        className="flex items-center gap-3 px-3 py-1.5"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[11px]">{perm.name}</span>
                            <Badge
                              variant="outline"
                              className={`text-[7px] h-3.5 px-1 ${SCOPE_COLORS[perm.scope]}`}
                            >
                              {perm.scope}
                            </Badge>
                          </div>
                          {perm.details && (
                            <p className="text-[9px] text-muted-foreground mt-0.5">
                              {perm.details}
                            </p>
                          )}
                        </div>
                        <Switch
                          checked={perm.allowed}
                          onCheckedChange={(v) => handleToggle(perm.id, v)}
                          disabled={saving}
                          className="scale-75 shrink-0"
                        />
                      </div>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Summary */}
        {profile && (
          <div className="flex items-center gap-2 pt-2 border-t border-border/10">
            <span className="text-[9px] text-muted-foreground">
              {profile.permissions.filter((p) => p.allowed).length} of{" "}
              {profile.permissions.length} permissions granted
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-5 text-[9px] ml-auto"
              disabled={saving}
              onClick={() => handleBatchToggle(true)}
              aria-label="Accorder toutes les permissions"
            >
              <Check size={9} className="mr-0.5" />
              {saving ? "..." : "Grant All"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-5 text-[9px]"
              disabled={saving}
              onClick={() => handleBatchToggle(false)}
              aria-label="Revoquer toutes les permissions"
            >
              <X size={9} className="mr-0.5" />
              {saving ? "..." : "Revoke All"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
