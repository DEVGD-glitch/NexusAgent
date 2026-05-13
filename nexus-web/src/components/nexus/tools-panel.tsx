"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/nexus-api";
import { Wrench, Search, Loader2, Terminal, Database, Globe, FileText, Shield, Network, Webhook } from "lucide-react";
import { toast } from "sonner";

interface ToolDef {
  name: string;
  category: string;
  params: { name: string; type: string; required: boolean }[];
}

const TOOLS: ToolDef[] = [
  { name: "search_memory", category: "Mémoire", params: [{ name: "query", type: "string", required: true }, { name: "namespace", type: "string", required: false }, { name: "top_k", type: "number", required: false }] },
  { name: "store_memory", category: "Mémoire", params: [{ name: "text", type: "string", required: true }, { name: "namespace", type: "string", required: false }] },
  { name: "knowledge_query", category: "Connaissances", params: [{ name: "entity_name", type: "string", required: true }, { name: "depth", type: "number", required: false }] },
  { name: "knowledge_search", category: "Connaissances", params: [{ name: "query", type: "string", required: true }] },
  { name: "knowledge_add_entity", category: "Connaissances", params: [{ name: "name", type: "string", required: true }, { name: "entity_type", type: "string", required: false }] },
  { name: "web_search", category: "Web", params: [{ name: "query", type: "string", required: true }, { name: "num_results", type: "number", required: false }] },
  { name: "reason_react", category: "Raisonnement", params: [{ name: "task", type: "string", required: true }] },
  { name: "reason_tot", category: "Raisonnement", params: [{ name: "task", type: "string", required: true }] },
  { name: "read_file", category: "Fichiers", params: [{ name: "path", type: "string", required: true }] },
  { name: "list_files", category: "Fichiers", params: [{ name: "directory", type: "string", required: false }] },
  { name: "audit_query", category: "Système", params: [{ name: "limit", type: "number", required: false }] },
  { name: "install_package", category: "Code", params: [{ name: "package", type: "string", required: true }] },
  { name: "spawn_agent", category: "Agents", params: [{ name: "task", type: "string", required: true }, { name: "agent_type", type: "string", required: false }] },
];

const CATEGORIES = ["Mémoire", "Connaissances", "Web", "Raisonnement", "Fichiers", "Code", "Agents", "Système"];
const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Mémoire: Database, Connaissances: Network, Web: Globe,
  Raisonnement: Terminal, Fichiers: FileText, Code: Terminal,
  Agents: Webhook, Système: Shield,
};

export function ToolsPanel() {
  const [selectedTool, setSelectedTool] = useState<ToolDef | null>(null);
  const [params, setParams] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState("Mémoire");

  const filteredTools = TOOLS.filter((t) => t.category === activeCategory);

  function selectTool(tool: ToolDef) {
    setSelectedTool(tool);
    setParams({});
    setResult(null);
  }

  async function handleExecute() {
    if (!selectedTool) return;
    setLoading(true);
    setResult(null);
    try {
      const body: Record<string, unknown> = { ...params };
      const data = await api.genericTool(selectedTool.name, body);
      setResult(data as Record<string, unknown>);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-48 border-r border-border p-2 space-y-1">
        {CATEGORIES.map((cat) => {
          const Icon = CATEGORY_ICONS[cat] || Wrench;
          return (
            <Button
              key={cat}
              variant={activeCategory === cat ? "secondary" : "ghost"}
              size="sm"
              className="w-full justify-start text-xs h-8 gap-2"
              onClick={() => setActiveCategory(cat)}
            >
              <Icon size={14} />
              {cat}
            </Button>
          );
        })}
      </div>

      <div className="w-48 border-r border-border p-2 space-y-1">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium px-1 mb-1">
          {activeCategory}
        </p>
        {filteredTools.map((tool) => (
          <Button
            key={tool.name}
            variant={selectedTool?.name === tool.name ? "secondary" : "ghost"}
            size="sm"
            className="w-full justify-start text-xs h-7"
            onClick={() => selectTool(tool)}
          >
            {tool.name.replace(/_/g, " ")}
          </Button>
        ))}
      </div>

      <div className="flex-1 flex flex-col">
        {selectedTool ? (
          <>
            <div className="p-3 border-b border-border">
              <h3 className="text-sm font-medium capitalize">{selectedTool.name.replace(/_/g, " ")}</h3>
              <div className="flex gap-1 mt-1">
                {selectedTool.params.filter((p) => p.required).map((p) => (
                  <Badge key={p.name} variant="outline" className="text-[10px]">{p.name}</Badge>
                ))}
              </div>
            </div>

            <ScrollArea className="flex-1 p-3 space-y-2">
              {selectedTool.params.map((param) => (
                <div key={param.name}>
                  <label className="text-xs text-muted-foreground">
                    {param.name} {param.required && <span className="text-destructive">*</span>}
                  </label>
                  <Input
                    value={params[param.name] || ""}
                    onChange={(e) => setParams((p) => ({ ...p, [param.name]: e.target.value }))}
                    placeholder={param.type}
                    className="h-8 text-xs mt-0.5"
                  />
                </div>
              ))}

              <Button onClick={handleExecute} disabled={loading} size="sm" className="w-full gap-1 text-xs">
                {loading ? <Loader2 size={12} className="animate-spin" /> : <Wrench size={12} />}
                Exécuter
              </Button>

              {result !== null && (
                <Card>
                  <CardContent className="p-3">
                    <pre className="text-xs whitespace-pre-wrap overflow-auto max-h-64">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </ScrollArea>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            Sélectionnez un outil
          </div>
        )}
      </div>
    </div>
  );
}
