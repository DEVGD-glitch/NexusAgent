// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Knowledge Panel
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState } from "react";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Search, Globe, GitBranch } from "lucide-react";
import type { KnowledgeEntity } from "@/types/nexus";

export function KnowledgePanel() {
  const [query, setQuery] = useState("");
  const [entities, setEntities] = useState<KnowledgeEntity[]>([]);
  const [searching, setSearching] = useState(false);
  const [webQuery, setWebQuery] = useState("");
  const [webResults, setWebResults] = useState<{ title: string; url: string; snippet: string }[]>([]);
  const [webSearching, setWebSearching] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await nexusApi.knowledgeSearch(query);
      setEntities(res);
    } catch {
      setEntities([]);
    } finally {
      setSearching(false);
    }
  };

  const handleWebSearch = async () => {
    if (!webQuery.trim()) return;
    setWebSearching(true);
    try {
      const res = await nexusApi.webSearch(webQuery, 8);
      setWebResults(res.results);
    } catch {
      setWebResults([]);
    } finally {
      setWebSearching(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Connaissances</h1>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Knowledge Graph Search */}
        <Card className="border-border/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2"><GitBranch size={14} />Graphe de Connaissances</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher des entites..."
                className="flex-1 h-9 rounded-md border border-border/40 bg-muted/20 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <Button onClick={handleSearch} disabled={searching} size="sm">
                {searching ? "..." : "Chercher"}
              </Button>
            </div>

            {entities.length > 0 && (
              <div className="mt-3 space-y-2 max-h-60 overflow-y-auto">
                {entities.map((e, i) => (
                  <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/20">
                    <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate">{e.name}</p>
                      <Badge variant="outline" className="text-[9px]">{e.type}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Web Search */}
        <Card className="border-border/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2"><Globe size={14} />Recherche Web</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <input
                value={webQuery}
                onChange={(e) => setWebQuery(e.target.value)}
                placeholder="Rechercher sur le web..."
                className="flex-1 h-9 rounded-md border border-border/40 bg-muted/20 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
                onKeyDown={(e) => e.key === "Enter" && handleWebSearch()}
              />
              <Button onClick={handleWebSearch} disabled={webSearching} size="sm">
                {webSearching ? "..." : "Chercher"}
              </Button>
            </div>

            {webResults.length > 0 && (
              <div className="mt-3 space-y-2 max-h-80 overflow-y-auto">
                {webResults.map((r, i) => (
                  <a key={i} href={r.url} target="_blank" rel="noopener noreferrer" className="block p-2 rounded-lg bg-muted/20 border border-border/20 hover:bg-muted/30 transition-colors">
                    <p className="text-xs font-medium text-primary truncate">{r.title}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">{r.snippet}</p>
                    <p className="text-[9px] text-muted-foreground/60 mt-1 truncate">{r.url}</p>
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
