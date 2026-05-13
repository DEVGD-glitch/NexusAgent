// ═══════════════════════════════════════════════════════════════
// NEXUS — Code Workspace (Integrated, not separate panel)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState } from "react";
import { nexusApi } from "@/lib/nexus-api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Code2, Play, Loader2, Terminal } from "lucide-react";
import type { CodeResult } from "@/types/nexus";

export function CodeWorkspace() {
  const [code, setCode] = useState("# Code Python\nprint('Bonjour depuis NEXUS!')\n");
  const [language, setLanguage] = useState("python");
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<CodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExecute = async () => {
    setExecuting(true);
    setError(null);
    setResult(null);
    try {
      const res = await nexusApi.executeCode(code, language, 30, true);
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur d'execution");
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-border/20 shrink-0">
        <div className="flex items-center gap-2 text-xs">
          <Code2 size={13} className="text-primary" />
          <span className="font-medium">Code</span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-6 rounded border border-border/30 bg-muted/20 px-1.5 text-[10px]"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="bash">Bash</option>
          </select>
        </div>
        <Button onClick={handleExecute} disabled={executing} size="sm" className="h-6 text-[10px] gap-1 px-2">
          {executing ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
          Run
        </Button>
      </div>

      {/* Editor + Output */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Tabs defaultValue="editor" className="flex-1 flex flex-col">
          <TabsList className="mx-3 mt-1.5 w-fit h-7">
            <TabsTrigger value="editor" className="text-[10px] gap-1 h-6 px-2"><Code2 size={10} />Editeur</TabsTrigger>
            <TabsTrigger value="output" className="text-[10px] gap-1 h-6 px-2"><Terminal size={10} />Sortie</TabsTrigger>
          </TabsList>

          <TabsContent value="editor" className="flex-1 p-3 pt-1">
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full h-full min-h-[300px] rounded-lg border border-border/20 bg-muted/10 p-3 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none"
              spellCheck={false}
            />
          </TabsContent>

          <TabsContent value="output" className="flex-1 p-3 pt-1">
            {error && (
              <pre className="text-xs text-red-400 bg-red-500/5 p-3 rounded-lg border border-red-500/20 whitespace-pre-wrap">{error}</pre>
            )}
            {result && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant={result.exit_code === 0 ? "default" : "destructive"} className="text-[9px]">Exit {result.exit_code}</Badge>
                  <span className="text-[9px] text-muted-foreground">{result.execution_time_ms}ms</span>
                  {result.timed_out && <Badge variant="destructive" className="text-[9px]">Timeout</Badge>}
                </div>
                {result.stdout && (
                  <pre className="text-xs font-mono text-emerald-400 bg-emerald-500/5 p-2 rounded whitespace-pre-wrap border border-emerald-500/15">{result.stdout}</pre>
                )}
                {result.stderr && (
                  <pre className="text-xs font-mono text-red-400 bg-red-500/5 p-2 rounded whitespace-pre-wrap border border-red-500/15">{result.stderr}</pre>
                )}
              </div>
            )}
            {!result && !error && (
              <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                <Terminal size={20} className="mb-2 opacity-30" />
                <p className="text-[11px]">Executez du code pour voir le resultat</p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
