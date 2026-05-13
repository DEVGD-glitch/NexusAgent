"use client";

import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/nexus-api";
import { ListChecks, Play, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface TaskResult {
  result: string;
  status: string;
  plan: string;
}

export function TasksPanel() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<TaskResult[]>([]);

  async function handleRun() {
    const task = input.trim();
    if (!task || loading) return;
    setInput("");
    setLoading(true);
    try {
      const data = await api.runTask(task);
      setResults((prev) => [data, ...prev]);
    } catch {
      setResults((prev) => [{ result: "Erreur d'exécution", status: "error", plan: "" }, ...prev]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-border p-3 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-1">
          <ListChecks size={14} /> Tâches
        </h2>
        <p className="text-xs text-muted-foreground">
          Décrivez une tâche complexe. NEXUS va planifier, exécuter et réfléchir au résultat.
        </p>
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ex: Analyse le code de mon projet et trouve les bugs..."
          className="min-h-[100px] text-sm resize-none"
        />
        <Button
          onClick={handleRun}
          disabled={loading || !input.trim()}
          className="w-full gap-1"
          size="sm"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Exécuter la tâche
        </Button>
      </div>

      <div className="flex-1">
        <ScrollArea className="h-full p-3">
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Aucune tâche exécutée
            </p>
          ) : (
            <div className="space-y-3">
              {results.map((r, i) => (
                <Card key={i}>
                  <CardContent className="p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      {r.status === "completed" || r.status === "success" ? (
                        <CheckCircle2 size={14} className="text-green-500" />
                      ) : (
                        <XCircle size={14} className="text-red-500" />
                      )}
                      <Badge variant={r.status === "completed" || r.status === "success" ? "default" : "destructive"} className="text-[10px]">
                        {r.status}
                      </Badge>
                    </div>
                    {r.plan && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Plan :</p>
                        <pre className="text-xs bg-muted p-2 rounded whitespace-pre-wrap">{r.plan}</pre>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Résultat :</p>
                      <p className="text-sm whitespace-pre-wrap">{r.result}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
