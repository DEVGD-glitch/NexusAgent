"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/nexus-api";
import { Search, Network, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface KGEntity {
  name: string;
  type: string;
  properties: Record<string, unknown>;
}

interface KGRelation {
  source: string;
  target: string;
  relation: string;
}

interface KGResult {
  entity: KGEntity | null;
  relationships: KGRelation[];
  neighbors: unknown[];
}

export function KnowledgePanel() {
  const [query, setQuery] = useState("");
  const [entityName, setEntityName] = useState("");
  const [entityType, setEntityType] = useState("concept");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<KGResult | null>(null);
  const [searchResults, setSearchResults] = useState<Record<string, unknown>[] | null>(null);

  async function handleQuery() {
    if (!entityName.trim()) return;
    setLoading(true);
    try {
      const data = await api.knowledgeQuery(entityName);
      setResult(data);
      setSearchResults(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.knowledgeSearch(query);
      setSearchResults(data as unknown as Record<string, unknown>[]);
      setResult(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-60 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <Network size={14} /> Graphe de connaissances
        </h2>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Rechercher une entité</p>
          <div className="flex gap-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nom..."
              className="h-8 text-xs"
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <Button size="icon" className="size-8" onClick={handleSearch} disabled={loading}>
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            </Button>
          </div>
        </div>

        <Separator />

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Consulter une entité</p>
          <div className="flex gap-1">
            <Input
              value={entityName}
              onChange={(e) => setEntityName(e.target.value)}
              placeholder="Entité..."
              className="h-8 text-xs"
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            />
            <Button size="icon" className="size-8" onClick={handleQuery} disabled={loading}>
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Network size={14} />}
            </Button>
          </div>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="w-full bg-muted border border-border rounded px-2 py-1 text-xs"
          >
            <option value="concept">Concept</option>
            <option value="person">Personne</option>
            <option value="technology">Technologie</option>
            <option value="place">Lieu</option>
            <option value="event">Événement</option>
          </select>
        </div>
      </div>

      <div className="flex-1">
        <ScrollArea className="h-full p-3">
          {searchResults && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">{searchResults.length} résultat(s)</p>
              {searchResults.map((entity, i) => (
                <Card key={i}>
                  <CardContent className="p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{entity.name as string}</span>
                      <Badge variant="outline" className="text-[10px]">{entity.type as string}</Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <Card>
                <CardContent className="p-3">
                  <h3 className="text-sm font-medium">{result.entity?.name || "Inconnu"}</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    Type : {result.entity?.type || "-"}
                  </p>
                </CardContent>
              </Card>

              {result.relationships.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Relations</p>
                  {result.relationships.map((rel, i) => (
                    <Card key={i} className="mb-1">
                      <CardContent className="p-2 text-xs">
                        {rel.source} —<strong>{rel.relation}</strong>— {rel.target}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {!searchResults && !result && (
            <p className="text-sm text-muted-foreground text-center py-8">
              Recherchez ou consultez une entité dans le graphe de connaissances
            </p>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
