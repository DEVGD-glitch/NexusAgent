import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { FileCode, Plus, Minus } from "lucide-react";

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  oldLineNum?: number;
  newLineNum?: number;
  content: string;
}

interface DiffSection {
  header: string;
  lines: DiffLine[];
}

interface DiffViewProps {
  filePath: string;
  oldCode: string;
  newCode: string;
  language?: string;
}

function lcsDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  const m = oldLines.length;
  const n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const result: DiffLine[] = [];
  let i = m, j = n;
  const stack: DiffLine[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      stack.push({ type: "unchanged", oldLineNum: i, newLineNum: j, content: oldLines[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      stack.push({ type: "added", newLineNum: j, content: newLines[j - 1] });
      j--;
    } else {
      stack.push({ type: "removed", oldLineNum: i, content: oldLines[i - 1] });
      i--;
    }
  }

  while (stack.length > 0) {
    result.push(stack.pop()!);
  }

  return result;
}

function groupSections(lines: DiffLine[]): DiffSection[] {
  const sections: DiffSection[] = [];
  let i = 0;

  while (i < lines.length) {
    if (lines[i].type === "unchanged") {
      let start = i;
      while (i < lines.length && lines[i].type === "unchanged") i++;
      const group = lines.slice(start, i);
      const oldStart = group[0].oldLineNum ?? 0;
      const newStart = group[0].newLineNum ?? 0;
      const count = group.length;
      sections.push({
        header: `@@ -${oldStart},${count} +${newStart},${count} @@`,
        lines: group,
      });
    } else {
      const changeStart = i;
      while (i < lines.length && lines[i].type !== "unchanged") i++;
      const group = lines.slice(changeStart, i);
      const firstRemoved = group.find((l) => l.type === "removed");
      const firstAdded = group.find((l) => l.type === "added");
      const oldStart = firstRemoved?.oldLineNum ?? firstAdded?.newLineNum ?? 0;
      const newStart = firstAdded?.newLineNum ?? firstRemoved?.oldLineNum ?? 0;
      const removedCount = group.filter((l) => l.type === "removed").length;
      const addedCount = group.filter((l) => l.type === "added").length;
      sections.push({
        header: `@@ -${oldStart},${removedCount} +${newStart},${addedCount} @@`,
        lines: group,
      });
    }
  }

  return sections;
}

function countStats(lines: DiffLine[]) {
  let added = 0;
  let removed = 0;
  for (const line of lines) {
    if (line.type === "added") added++;
    if (line.type === "removed") removed++;
  }
  return { added, removed };
}

export function DiffView({ filePath, oldCode, newCode, language }: DiffViewProps) {
  const diff = useMemo(() => {
    const oldLines = oldCode === "" ? [] : oldCode.split("\n");
    const newLines = newCode === "" ? [] : newCode.split("\n");
    return lcsDiff(oldLines, newLines);
  }, [oldCode, newCode]);

  const sections = useMemo(() => groupSections(diff), [diff]);
  const stats = useMemo(() => countStats(diff), [diff]);
  const hasChanges = stats.added > 0 || stats.removed > 0;

  const isEmpty = oldCode === "" && newCode === "";

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground animate-in fade-in duration-300">
        <FileCode className="h-10 w-10 mb-3 opacity-40" />
        <p className="text-sm font-medium">Aucune modification</p>
        <p className="text-xs mt-1 opacity-60">Le fichier n&apos;a pas été modifié</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between gap-2 px-4 py-2.5 bg-zinc-900/80 border-b border-zinc-800">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="h-4 w-4 text-blue-400 shrink-0" />
          <span className="text-sm font-mono text-zinc-200 truncate">{filePath}</span>
          {language && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-zinc-700 text-zinc-400 font-mono">
              {language}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {stats.added > 0 && (
            <span className="flex items-center gap-1 text-xs font-mono text-emerald-400">
              <Plus className="h-3 w-3" />+{stats.added}
            </span>
          )}
          {stats.removed > 0 && (
            <span className="flex items-center gap-1 text-xs font-mono text-red-400">
              <Minus className="h-3 w-3" />-{stats.removed}
            </span>
          )}
          {!hasChanges && (
            <span className="text-xs font-mono text-zinc-500">aucun changement</span>
          )}
        </div>
      </div>

      <ScrollArea className="max-h-[500px]">
        <div className="min-w-0">
          {sections.map((section, si) => (
            <div key={si} className="animate-in fade-in duration-200" style={{ animationDelay: `${si * 30}ms` }}>
              <div className="flex items-center gap-2 px-4 py-1 bg-zinc-900/60 border-b border-zinc-800/50">
                <span className="text-xs font-mono text-purple-400/80 tabular-nums">{section.header}</span>
              </div>
              {section.lines.map((line, li) => {
                const isAdded = line.type === "added";
                const isRemoved = line.type === "removed";
                return (
                  <div
                    key={`${si}-${li}`}
                    className={cn(
                      "flex font-mono text-[13px] leading-6 border-b border-zinc-900/30 transition-colors",
                      isAdded && "bg-emerald-500/8 border-l-2 border-l-emerald-500",
                      isRemoved && "bg-red-500/8 border-l-2 border-l-red-500",
                      !isAdded && !isRemoved && "border-l-2 border-l-transparent hover:bg-zinc-900/30"
                    )}
                  >
                    <div className="flex w-12 shrink-0 select-none">
                      <span className="w-6 text-right pr-1 text-xs text-zinc-600 tabular-nums">
                        {line.oldLineNum ?? ""}
                      </span>
                      <span className="w-6 text-right pr-1 text-xs text-zinc-600 tabular-nums">
                        {line.newLineNum ?? ""}
                      </span>
                    </div>
                    <span className="w-5 shrink-0 text-center select-none text-xs leading-6">
                      {isAdded && <span className="text-emerald-500">+</span>}
                      {isRemoved && <span className="text-red-500">-</span>}
                      {!isAdded && !isRemoved && <span className="text-zinc-700">&nbsp;</span>}
                    </span>
                    <span
                      className={cn(
                        "flex-1 pr-4 overflow-x-auto whitespace-pre",
                        isAdded && "text-emerald-200/90",
                        isRemoved && "text-red-200/90",
                        !isAdded && !isRemoved && "text-zinc-300"
                      )}
                    >
                      {line.content || <span className="opacity-0">.</span>}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
