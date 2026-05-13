"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { api, type AuditEntry } from "@/lib/nexus-api";
import { Shield, RefreshCw, Loader2 } from "lucide-react";

export function SecurityPanel() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.auditLog(50);
      setEntries(data.entries);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="flex h-full">
      <div className="w-56 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <Shield size={14} /> Sécurité
        </h2>
        <p className="text-xs text-muted-foreground">
          Journal d'audit de toutes les actions effectuées par NEXUS.
        </p>
        <Button variant="outline" size="sm" className="w-full h-7 text-xs gap-1" onClick={fetchLogs} disabled={loading}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Actualiser
        </Button>
      </div>

      <div className="flex-1">
        <ScrollArea className="h-full">
          <div className="p-2 space-y-1">
            {entries.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Aucune entrée d'audit
              </p>
            ) : (
              entries.map((entry, i) => (
                <Card key={i}>
                  <CardContent className="p-2 flex items-center gap-2 text-xs">
                    <Badge
                      variant={entry.outcome === "success" ? "default" : "destructive"}
                      className="text-[10px] shrink-0"
                    >
                      {entry.outcome}
                    </Badge>
                    <span className="font-medium shrink-0">{entry.action}</span>
                    <span className="text-muted-foreground truncate">{entry.target}</span>
                    <span className="text-muted-foreground ml-auto shrink-0 text-[10px]">
                      {new Date(entry.timestamp).toLocaleTimeString("fr-FR")}
                    </span>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
