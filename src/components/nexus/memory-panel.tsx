// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Memory Panel
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect } from "react";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Brain, Search, Plus, Database } from "lucide-react";
import type { MemoryEntry, MemoryNamespace } from "@/types/nexus";

export function MemoryPanel() {
  const [namespaces, setNamespaces] = useState<MemoryNamespace[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [storeText, setStoreText] = useState("");
  const [storeNs, setStoreNs] = useState("knowledge");
  const [searching, setSearching] = useState(false);
  const [storing, setStoring] = useState(false);

  useEffect(() => {
    nexusApi.memoryStats().then((data) => {
      const ns: MemoryNamespace[] = Object.entries(data.namespaces).map(([name, info]) => ({
        name,
        count: (info as { count: number }).count,
      }));
      setNamespaces(ns);
    }).catch(() => {});
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await nexusApi.searchMemory(query, "knowledge", 10);
      setResults(res);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleStore = async () => {
    if (!storeText.trim()) return;
    setStoring(true);
    try {
      await nexusApi.storeMemory(storeText, storeNs);
      setStoreText("");
      // Refresh stats
      const data = await nexusApi.memoryStats();
      const ns: MemoryNamespace[] = Object.entries(data.namespaces).map(([name, info]) => ({
        name,
        count: (info as { count: number }).count,
      }));
      setNamespaces(ns);
    } catch {} finally {
      setStoring(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Memoire</h1>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Namespaces */}
        <div className="space-y-2">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Namespaces</h3>
          <div className="grid grid-cols-3 gap-2">
            {namespaces.map((ns) => (
              <div key={ns.name} className="flex items-center gap-2 p-2 rounded-lg border border-border/30 bg-muted/10">
                <Database size={14} className="text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate">{ns.name}</p>
                  <p className="text-[10px] text-muted-foreground">{ns.count} docs</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Search */}
        <Card className="border-border/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2"><Search size={14} />Rechercher</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher dans la memoire..."
                className="flex-1 h-9 rounded-md border border-border/40 bg-muted/20 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <Button onClick={handleSearch} disabled={searching} size="sm">
                {searching ? "..." : "Chercher"}
              </Button>
            </div>

            {results.length > 0 && (
              <div className="mt-3 space-y-2 max-h-60 overflow-y-auto">
                {results.map((r, i) => (
                  <div key={i} className="p-2 rounded-lg bg-muted/20 border border-border/20">
                    <p className="text-xs line-clamp-3">{r.text}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className="text-[9px]">{String(r.metadata?.source || "unknown")}</Badge>
                      <span className="text-[9px] text-muted-foreground">distance: {r.distance.toFixed(3)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Store */}
        <Card className="border-border/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2"><Plus size={14} />Stocker</CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              value={storeText}
              onChange={(e) => setStoreText(e.target.value)}
              placeholder="Texte a memoriser..."
              className="w-full h-24 rounded-md border border-border/40 bg-muted/20 p-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
            <div className="flex items-center gap-2 mt-2">
              <select
                value={storeNs}
                onChange={(e) => setStoreNs(e.target.value)}
                className="h-8 rounded-md border border-border/40 bg-muted/20 px-2 text-xs"
              >
                <option value="knowledge">knowledge</option>
                <option value="conversations">conversations</option>
                <option value="episodes">episodes</option>
                <option value="skills">skills</option>
                <option value="identity">identity</option>
                <option value="code">code</option>
              </select>
              <Button onClick={handleStore} disabled={storing} size="sm" className="ml-auto">
                {storing ? "..." : "Stocker"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
