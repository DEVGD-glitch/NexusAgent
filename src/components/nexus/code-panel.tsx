// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Code Panel (Workspace + Executor)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState } from "react";
import { nexusApi } from "@/lib/nexus-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Code2, Play, Loader2, Terminal, File } from "lucide-react";
import type { CodeResult } from "@/types/nexus";

export function CodePanel() {
  const [code, setCode] = useState("# Ecrivez votre code Python ici\nprint('Bonjour depuis NEXUS!')\n");
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
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          <Code2 size={16} className="text-primary" />
          <h1 className="text-sm font-semibold">Code</h1>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-7 rounded-md border border-border/40 bg-muted/20 px-2 text-xs"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="bash">Bash</option>
          </select>
          <Button onClick={handleExecute} disabled={executing} size="sm" className="gap-1.5 h-7 text-xs">
            {executing ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            Executer
          </Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <Tabs defaultValue="editor" className="flex-1 flex flex-col">
          <TabsList className="mx-4 mt-2 w-fit">
            <TabsTrigger value="editor" className="text-xs gap-1"><Code2 size={12} />Editeur</TabsTrigger>
            <TabsTrigger value="output" className="text-xs gap-1"><Terminal size={12} />Sortie</TabsTrigger>
          </TabsList>

          <TabsContent value="editor" className="flex-1 p-4 pt-2">
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full h-full min-h-[300px] rounded-lg border border-border/40 bg-muted/10 p-3 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
              spellCheck={false}
            />
          </TabsContent>

          <TabsContent value="output" className="flex-1 p-4 pt-2">
            {error && (
              <Card className="border-red-500/30 bg-red-500/5">
                <CardContent className="p-3">
                  <p className="text-xs text-red-400 font-medium">Erreur</p>
                  <pre className="text-xs text-red-300 mt-1 whitespace-pre-wrap">{error}</pre>
                </CardContent>
              </Card>
            )}

            {result && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant={result.exit_code === 0 ? "default" : "destructive"} className="text-[10px]">
                    Exit {result.exit_code}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground">{result.execution_time_ms}ms</span>
                  {result.timed_out && <Badge variant="destructive" className="text-[10px]">Timeout</Badge>}
                </div>

                {result.stdout && (
                  <Card className="border-border/30">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs flex items-center gap-1.5"><Terminal size={12} />stdout</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <pre className="text-xs font-mono whitespace-pre-wrap text-emerald-400 bg-emerald-500/5 p-2 rounded">{result.stdout}</pre>
                    </CardContent>
                  </Card>
                )}

                {result.stderr && (
                  <Card className="border-border/30">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs flex items-center gap-1.5"><Terminal size={12} />stderr</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <pre className="text-xs font-mono whitespace-pre-wrap text-red-400 bg-red-500/5 p-2 rounded">{result.stderr}</pre>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}

            {!result && !error && (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                <Terminal size={24} className="mb-2 opacity-30" />
                <p className="text-xs">Executez du code pour voir le resultat</p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
