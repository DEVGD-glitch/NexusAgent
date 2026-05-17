// ═══════════════════════════════════════════════════════════════
// NEXUS — Plugin Manager (Modale d'installation & gestion)
// Gestion des plugins: liste, recherche, activation, installation
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
  Puzzle,
  Package,
  Plus,
  Search,
  AlertCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  status: "enabled" | "disabled" | "error";
  author: string;
}

interface PluginManagerProps {
  open: boolean;
  onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────────

const STATUS_CONFIG = {
  enabled: {
    dot: "bg-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    label: "Actif",
  },
  disabled: {
    dot: "bg-muted-foreground/40",
    badge: "bg-muted/20 text-muted-foreground border-border/10",
    label: "Inactif",
  },
  error: {
    dot: "bg-red-500",
    badge: "bg-red-500/10 text-red-400 border-red-500/20",
    label: "Erreur",
  },
} as const;

// ── Component ──────────────────────────────────────────────────

export function PluginManager({ open, onClose }: PluginManagerProps) {
  // ── State ──
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [installOpen, setInstallOpen] = useState(false);
  const [installUrl, setInstallUrl] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);

  // ── Fetch plugins ──
  const fetchPlugins = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/plugins");
      if (!res.ok) {
        throw new Error(`Erreur ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setPlugins(Array.isArray(data) ? data : data.plugins ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Impossible de charger les plugins");
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchPlugins();
  }, [open, fetchPlugins]);

  // ── Filtered list ──
  const filteredPlugins = useMemo(
    () =>
      search
        ? plugins.filter((p) =>
            p.name.toLowerCase().includes(search.toLowerCase())
          )
        : plugins,
    [plugins, search]
  );

  // ── Toggle plugin ──
  const handleToggle = useCallback(
    async (plugin: PluginInfo) => {
      const newStatus = plugin.status === "enabled" ? "disabled" : "enabled";
      setTogglingIds((prev) => new Set(prev).add(plugin.id));

      try {
        const res = await fetch("/api/plugins", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pluginId: plugin.id, status: newStatus, action: "toggle" }),
        });

        if (!res.ok) {
          throw new Error(`Erreur ${res.status}`);
        }

        setPlugins((prev) =>
          prev.map((p) =>
            p.id === plugin.id ? { ...p, status: newStatus } : p
          )
        );
      } catch {
        // Optimistic revert on failure
        setPlugins((prev) =>
          prev.map((p) =>
            p.id === plugin.id ? { ...p, status: "error" } : p
          )
        );
      } finally {
        setTogglingIds((prev) => {
          const next = new Set(prev);
          next.delete(plugin.id);
          return next;
        });
      }
    },
    []
  );

  // ── Install plugin ──
  const handleInstall = useCallback(async () => {
    if (!installUrl.trim()) return;
    setInstalling(true);
    setInstallError(null);

    try {
      const res = await fetch("/api/plugins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: installUrl.trim(), action: "install" }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Erreur ${res.status}`);
      }

      const newPlugin = await res.json();
      if (newPlugin && newPlugin.id) {
        setPlugins((prev) => [...prev, newPlugin]);
      }

      setInstallOpen(false);
      setInstallUrl("");
    } catch (err: unknown) {
      setInstallError(
        err instanceof Error ? err.message : "Echec de l'installation"
      );
    } finally {
      setInstalling(false);
    }
  }, [installUrl]);

  // ── Keyboard shortcut ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !installOpen) {
        onClose();
      }
    };
    if (open) {
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }
  }, [open, onClose, installOpen]);

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col p-0 gap-0">
          <DialogHeader className="p-4 pb-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Puzzle size={16} className="text-muted-foreground" />
                <DialogTitle className="text-sm font-semibold">
                  Gestionnaire de plugins
                </DialogTitle>
              </div>
              <Badge
                variant="outline"
                className="h-5 text-[9px] px-1.5 font-mono"
              >
                {plugins.length}
              </Badge>
            </div>
            <DialogDescription className="text-[10px] text-muted-foreground mt-1">
              Installez et gerez les extensions du NEXUS Agent
            </DialogDescription>
          </DialogHeader>

          {/* ── Actions bar ── */}
          <div className="flex items-center gap-2 px-4 pt-3 pb-2">
            <div className="relative flex-1">
              <Search
                size={12}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60 pointer-events-none"
              />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un plugin..."
                className="h-7 pl-7 text-[10px]"
              />
            </div>
            <Button
              size="sm"
              variant="default"
              className="h-7 text-[10px] gap-1 shrink-0"
              onClick={() => {
                setInstallError(null);
                setInstallUrl("");
                setInstallOpen(true);
              }}
            >
              <Plus size={12} />
              Installer
            </Button>
          </div>

          {/* ── Content ── */}
          <div className="flex-1 min-h-0 px-4 pb-4">
            {loading && (
              <div className="flex flex-col items-center justify-center py-10 gap-2" role="status" aria-live="polite">
                <Loader2 size={18} className="text-muted-foreground animate-spin" aria-hidden="true" />
                <span className="text-[10px] text-muted-foreground">
                  Chargement des plugins...
                </span>
              </div>
            )}

            {!loading && error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center py-10 gap-2"
                role="alert"
              >
                <AlertCircle size={18} className="text-red-400" aria-hidden="true" />
                <span className="text-[10px] text-red-400/80 text-center max-w-[250px]">
                  {error}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[9px] mt-1"
                  onClick={fetchPlugins}
                  aria-label="Reessayer le chargement des plugins"
                >
                  Reessayer
                </Button>
              </motion.div>
            )}

            {!loading && !error && filteredPlugins.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center py-10 gap-2"
              >
                <Package size={20} className="text-muted-foreground/30" />
                <span className="text-[10px] text-muted-foreground/60 text-center max-w-[220px]">
                  {search
                    ? "Aucun plugin ne correspond a votre recherche"
                    : "Aucun plugin installe. Cliquez sur \"Installer\" pour ajouter une extension."}
                </span>
              </motion.div>
            )}

            {!loading && !error && filteredPlugins.length > 0 && (
              <ScrollArea className="h-full max-h-[360px] pr-2">
                <AnimatePresence mode="popLayout">
                  {filteredPlugins.map((plugin, index) => {
                    const cfg = STATUS_CONFIG[plugin.status];
                    const isToggling = togglingIds.has(plugin.id);

                    return (
                      <motion.div
                        key={plugin.id}
                        layout
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                        transition={{ duration: 0.2, delay: index * 0.03 }}
                        className="flex items-start gap-3 p-2.5 rounded-lg border border-border/10 bg-muted/5 hover:bg-muted/10 transition-colors mb-1.5 group"
                      >
                        {/* Status dot */}
                        <div className="flex-shrink-0 pt-0.5">
                          <div
                            className={`w-2 h-2 rounded-full ${cfg.dot} transition-colors`}
                          />
                        </div>

                        {/* Plugin info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-medium truncate">
                              {plugin.name}
                            </span>
                            <span className="text-[8px] font-mono text-muted-foreground/50 shrink-0">
                              v{plugin.version}
                            </span>
                            <Badge
                              variant="outline"
                              className={`h-4 text-[7px] px-1.5 ${cfg.badge} shrink-0`}
                            >
                              {cfg.label}
                            </Badge>
                          </div>
                          <p className="text-[9px] text-muted-foreground/70 mt-0.5 line-clamp-1">
                            {plugin.description}
                          </p>
                          <span className="text-[8px] text-muted-foreground/40 mt-0.5 block">
                            par {plugin.author}
                          </span>
                        </div>

                        {/* Toggle switch */}
                        <div className="flex-shrink-0 pt-0.5">
                          {isToggling ? (
                            <Loader2
                              size={14}
                              className="text-muted-foreground animate-spin"
                            />
                          ) : (
                            <Switch
                              checked={plugin.status === "enabled"}
                              onCheckedChange={() => handleToggle(plugin)}
                              className="scale-75 origin-top-right"
                              disabled={plugin.status === "error"}
                            />
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </ScrollArea>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════
          INSTALL DIALOG (sub-dialog)
          ══════════════════════════════════════════════════════════ */}
      <Dialog open={installOpen} onOpenChange={(o) => !o && (setInstallOpen(false), setInstallError(null))}>
        <DialogContent className="sm:max-w-md p-4 gap-3">
          <DialogHeader className="p-0">
            <div className="flex items-center gap-2">
              <Package size={15} className="text-muted-foreground" />
              <DialogTitle className="text-sm font-semibold">
                Installer un plugin
              </DialogTitle>
            </div>
            <DialogDescription className="text-[10px] text-muted-foreground mt-1">
              Entrez le chemin local ou l'URL du plugin a installer
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <div className="relative">
              <ExternalLink
                size={12}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60 pointer-events-none"
              />
              <Input
                value={installUrl}
                onChange={(e) => {
                  setInstallUrl(e.target.value);
                  if (installError) setInstallError(null);
                }}
                placeholder="/chemin/vers/plugin ou https://..."
                className="h-8 pl-7 text-[10px] font-mono"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !installing && installUrl.trim()) {
                    handleInstall();
                  }
                }}
                autoFocus
              />
            </div>

            {installError && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-[9px] text-red-400 flex items-center gap-1"
              >
                <AlertCircle size={10} />
                {installError}
              </motion.p>
            )}
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-[10px]"
              onClick={() => {
                setInstallOpen(false);
                setInstallError(null);
                setInstallUrl("");
              }}
              disabled={installing}
            >
              Annuler
            </Button>
            <Button
              size="sm"
              variant="default"
              className="h-7 text-[10px] gap-1"
              onClick={handleInstall}
              disabled={!installUrl.trim() || installing}
            >
              {installing ? (
                <>
                  <Loader2 size={11} className="animate-spin" />
                  Installation...
                </>
              ) : (
                <>
                  <Package size={11} />
                  Installer
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
