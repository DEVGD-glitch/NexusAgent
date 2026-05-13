// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Security Panel
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Shield, FileText, Lock, AlertTriangle } from "lucide-react";

export function SecurityPanel() {
  const [auditEntries, setAuditEntries] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    nexusApi.auditLog(30).then((data) => {
      if (!cancelled) {
        setAuditEntries(data.entries);
        setLoading(false);
      }
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Securite</h1>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Security Features */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { icon: Lock, title: "Sandbox", desc: "Execution code isolee", active: true },
            { icon: Shield, title: "Guardrails", desc: "Validation entrees/sorties", active: true },
            { icon: FileText, title: "Audit", desc: "Journal immutable", active: true },
            { icon: AlertTriangle, title: "Rate Limiting", desc: "Protection surcharge", active: true },
          ].map((feat) => (
            <Card key={feat.title} className="border-border/30">
              <CardContent className="p-3 flex items-start gap-3">
                <feat.icon size={18} className="text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-medium">{feat.title}</p>
                  <p className="text-[10px] text-muted-foreground">{feat.desc}</p>
                  <Badge variant="default" className="text-[9px] mt-1">Actif</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Audit Log */}
        <Card className="border-border/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2"><FileText size={14} />Journal d'audit</CardTitle>
          </CardHeader>
          <CardContent>
            {auditEntries.length > 0 ? (
              <div className="space-y-1.5 max-h-80 overflow-y-auto">
                {auditEntries.map((entry: any, i) => (
                  <div key={i} className="flex items-center gap-2 p-1.5 rounded bg-muted/10 text-xs">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary/60 shrink-0" />
                    <span className="text-muted-foreground shrink-0">{entry.timestamp || ""}</span>
                    <span className="truncate">{entry.action || entry.category || JSON.stringify(entry).slice(0, 80)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                {loading ? "Chargement..." : "Aucune entree d'audit"}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
