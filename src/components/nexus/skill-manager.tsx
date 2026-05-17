// ═══════════════════════════════════════════════════════════════
// NEXUS — Skill Manager
// Toggle, scope, and manage agent skills
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
  Zap,
  Search,
  Globe,
  FolderOpen,
  Monitor,
  User,
  Loader2,
  AlertCircle,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────

export interface SkillInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  status: "enabled" | "disabled";
  scope: "global" | "workspace" | "session" | "agent";
  permissions: string[];
  hooks: string[];
  tools: string[];
}

interface SkillManagerProps {
  open: boolean;
  onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────────

const SCOPE_CONFIG = {
  global: {
    icon: Globe,
    color: "text-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  },
  workspace: {
    icon: FolderOpen,
    color: "text-blue-400",
    badge: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  },
  session: {
    icon: Monitor,
    color: "text-amber-400",
    badge: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  },
  agent: {
    icon: User,
    color: "text-violet-400",
    badge: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  },
} as const;

// ── Component ──────────────────────────────────────────────────

export function SkillManager({ open, onClose }: SkillManagerProps) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/skills");
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setSkills(data.skills ?? data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchSkills();
  }, [open, fetchSkills]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return skills.filter(
      (s) =>
        !q ||
        s.name.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    );
  }, [skills, search]);

  const [disableConfirmId, setDisableConfirmId] = useState<string | null>(null);

  const handleToggle = useCallback(async (skill: SkillInfo) => {
    const newStatus = skill.status === "enabled" ? "disabled" : "enabled";
    // Confirm before disabling
    if (newStatus === "disabled" && disableConfirmId !== skill.id) {
      setDisableConfirmId(skill.id);
      return;
    }
    setDisableConfirmId(null);
    setTogglingIds((prev) => new Set(prev).add(skill.id));
    try {
      const res = await fetch(`/api/skills/${skill.id}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setSkills((prev) =>
        prev.map((s) =>
          s.id === skill.id ? { ...s, status: newStatus as SkillInfo["status"] } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setTogglingIds((prev) => {
        const next = new Set(prev);
        next.delete(skill.id);
        return next;
      });
    }
  }, [disableConfirmId]);

  const enabledCount = skills.filter((s) => s.status === "enabled").length;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap size={16} className="text-amber-400" />
            Skills
            <Badge variant="outline" className="text-[9px] ml-auto">
              {enabledCount}/{skills.length} active
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Manage agent skills — toggle, scope, configure
          </DialogDescription>
        </DialogHeader>

        {/* Search */}
        <div className="relative">
          <Search
            size={12}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            placeholder="Search skills..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-7 h-7 text-[11px]"
          />
        </div>

        {error && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-500/10 border border-red-500/20 p-2 text-[10px] text-red-400">
            <AlertCircle size={10} />
            {error}
          </div>
        )}

        {/* Skill List */}
        <ScrollArea className="flex-1 max-h-[50vh]">
          {loading ? (
            <div className="flex items-center justify-center py-8" role="status" aria-live="polite">
              <Loader2 size={16} className="animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-[11px] text-muted-foreground text-center py-6">
              {search ? "No skills match your search" : "No skills available"}
            </p>
          ) : (
            <div className="space-y-1">
              <AnimatePresence>
                {filtered.map((skill) => {
                  const scopeConfig = SCOPE_CONFIG[skill.scope];
                  const ScopeIcon = scopeConfig.icon;
                  const isToggling = togglingIds.has(skill.id);
                  return (
                    <motion.div
                      key={skill.id}
                      layout
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="flex items-center gap-3 rounded-lg border border-border/10 bg-muted/5 p-2.5"
                    >
                      {/* Status dot */}
                      <div
                        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                          skill.status === "enabled"
                            ? "bg-emerald-500"
                            : "bg-muted-foreground/40"
                        }`}
                      />

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] font-medium truncate">
                            {skill.name}
                          </span>
                          <Badge
                            variant="outline"
                            className={`text-[7px] h-3.5 px-1 ${scopeConfig.badge}`}
                          >
                            <ScopeIcon size={7} className="mr-0.5" />
                            {skill.scope}
                          </Badge>
                        </div>
                        <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-1">
                          {skill.description}
                        </p>
                        {skill.tools.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {skill.tools.slice(0, 4).map((tool) => (
                              <Badge
                                key={tool}
                                variant="outline"
                                className="text-[7px] h-3 px-1 bg-muted/20"
                              >
                                {tool}
                              </Badge>
                            ))}
                            {skill.tools.length > 4 && (
                              <span className="text-[8px] text-muted-foreground">
                                +{skill.tools.length - 4}
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Toggle */}
                      {isToggling ? (
                        <Loader2
                          size={12}
                          className="animate-spin text-muted-foreground shrink-0"
                        />
                      ) : (
                        <Switch
                          checked={skill.status === "enabled"}
                          onCheckedChange={() => handleToggle(skill)}
                          className="scale-75 shrink-0"
                        />
                      )}
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
