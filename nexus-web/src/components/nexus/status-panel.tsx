"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type SystemStatus, type ProviderStatus } from "@/lib/nexus-api";
import { Activity, Server, Cpu, Globe } from "lucide-react";

export function StatusPanel() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([api.systemStatus(), api.providers()]);
      setStatus(s);
      setProviders(p);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur de connexion");
    }
  }, []);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, 10000);
    return () => clearInterval(interval);
  }, [fetch]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-destructive">
        <p>Impossible de contacter le backend : {error}</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <h2 className="text-sm font-semibold mb-4">Statut du système</h2>

      {status && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Card>
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Activity size={12} /> Statut
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <Badge variant={status.status === "running" ? "default" : "destructive"} className="mt-1">
                {status.status}
              </Badge>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Server size={12} /> Version
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <p className="text-sm font-semibold mt-1">{status.version}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Cpu size={12} /> Environnement
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <p className="text-sm font-semibold mt-1">{status.environment}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Globe size={12} /> Plateforme
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <p className="text-sm font-semibold mt-1">{status.platform}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {providers && (
        <div>
          <h3 className="text-sm font-medium mb-2">Fournisseurs LLM</h3>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(providers).map(([name, info]) => (
              <Card key={name} className={info.available ? "" : "opacity-50"}>
                <CardContent className="p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium capitalize">{name}</span>
                    <div className={`size-2 rounded-full ${info.available ? "bg-green-500" : "bg-red-500"}`} />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 truncate">{info.default_model}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
