"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api, type MemoryEntry } from "@/lib/nexus-api";
import { Search, Database, Loader2 } from "lucide-react";

const NAMESPACES = ["conversations", "episodes", "knowledge", "skills", "identity", "code"];

export function MemoryPanel() {
  const [query, setQuery] = useState("");
  const [namespace, setNamespace] = useState("knowledge");
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [stats, setStats] = useState<Record<string, { count: number }>>({});
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.memoryStats();
      setStats(data.namespaces);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  async function handleSearch() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const data = await api.searchMemory(query, namespace);
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-60 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <Database size={14} /> Mémoire vectorielle
        </h2>

        <div className="space-y-2">
          <Select value={namespace} onValueChange={(v) => v && setNamespace(v)}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {NAMESPACES.map((ns) => (
                <SelectItem key={ns} value={ns} className="text-xs">
                  {ns}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex gap-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher..."
              className="h-8 text-xs"
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <Button size="icon" className="size-8 shrink-0" onClick={handleSearch} disabled={searching}>
              {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            </Button>
          </div>
        </div>

        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium">Statistiques</p>
          {loading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            NAMESPACES.map((ns) => (
              <div key={ns} className="flex justify-between text-xs">
                <span className="text-muted-foreground truncate">{ns}</span>
                <Badge variant="outline" className="text-[10px] h-4 ml-1 shrink-0">
                  {stats[ns]?.count ?? 0}
                </Badge>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex-1">
        <ScrollArea className="h-full">
          <div className="p-3 space-y-2">
            {results.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {searching ? "Recherche..." : "Cherchez un document dans la mémoire vectorielle"}
              </p>
            ) : (
              results.map((entry, i) => (
                <Card key={entry.id || i}>
                  <CardContent className="p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-[10px]">
                        {entry.metadata?.source as string || "inconnu"}
                      </Badge>
                      <span className="text-muted-foreground">
                        distance: {entry.distance.toFixed(3)}
                      </span>
                    </div>
                    <p className="text-sm mt-1">{entry.text}</p>
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
