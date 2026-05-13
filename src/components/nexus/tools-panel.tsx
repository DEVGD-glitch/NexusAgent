// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Tools Panel
// ═══════════════════════════════════════════════════════════════

"use client";

import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Wrench, Brain, Globe, File, Terminal, GitBranch, Package, Shield } from "lucide-react";

const TOOL_CATEGORIES = [
  {
    name: "Memoire",
    icon: Brain,
    tools: [
      { name: "search_memory", desc: "Recherche vectorielle dans la memoire" },
      { name: "store_memory", desc: "Stocker du texte en memoire" },
      { name: "delete_memory", desc: "Supprimer un document memoire" },
    ],
  },
  {
    name: "Connaissances",
    icon: Globe,
    tools: [
      { name: "knowledge_query", desc: "Interroger le graphe de connaissances" },
      { name: "knowledge_search", desc: "Rechercher des entites" },
      { name: "knowledge_add_entity", desc: "Ajouter une entite" },
      { name: "knowledge_add_relation", desc: "Ajouter une relation" },
      { name: "web_search", desc: "Recherche web temps reel" },
    ],
  },
  {
    name: "Code & Fichiers",
    icon: Terminal,
    tools: [
      { name: "execute_code", desc: "Executer du code Python/JS/Bash" },
      { name: "execute_sandboxed", desc: "Executer en sandbox securise" },
      { name: "read_file", desc: "Lire un fichier" },
      { name: "write_file", desc: "Ecrire dans un fichier" },
      { name: "list_files", desc: "Lister les fichiers" },
    ],
  },
  {
    name: "Orchestration",
    icon: GitBranch,
    tools: [
      { name: "spawn_agent", desc: "Creer un sous-agent" },
      { name: "list_agents", desc: "Lister les agents" },
      { name: "run_pipeline", desc: "Executer un pipeline sequentiel" },
      { name: "run_parallel", desc: "Executer des taches en parallele" },
    ],
  },
  {
    name: "Raisonnement",
    icon: Brain,
    tools: [
      { name: "reason_react", desc: "Raisonnement ReAct" },
      { name: "reason_tot", desc: "Arbre de pensees" },
    ],
  },
  {
    name: "Systeme",
    icon: Shield,
    tools: [
      { name: "audit_query", desc: "Consulter le journal d'audit" },
      { name: "get_status", desc: "Statut du systeme" },
      { name: "install_package", desc: "Installer un paquet Python" },
    ],
  },
];

export function ToolsPanel() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Wrench size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Outils</h1>
        </div>
        <Badge variant="outline" className="text-[10px]">
          {TOOL_CATEGORIES.reduce((sum, c) => sum + c.tools.length, 0)} outils
        </Badge>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {TOOL_CATEGORIES.map((cat) => (
          <Card key={cat.name} className="border-border/30">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <cat.icon size={14} className="text-primary" />
                {cat.name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1.5">
                {cat.tools.map((tool) => (
                  <div key={tool.name} className="flex items-center gap-2 p-1.5 rounded-md hover:bg-muted/20 transition-colors">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary/60 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <code className="text-xs font-mono text-foreground/90">{tool.name}</code>
                      <p className="text-[10px] text-muted-foreground">{tool.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
