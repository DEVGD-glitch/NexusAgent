"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api, type CodeResult } from "@/lib/nexus-api";
import {
  Play, Loader2, Terminal, FolderClosed, File,
  FileJson, FileType, ChevronRight, ChevronDown,
  Minimize2, Monitor, X,
} from "lucide-react";

const LANGUAGES = ["python", "javascript", "typescript", "bash", "ruby", "go", "rust", "cpp"];

interface FileNode {
  name: string;
  type: "folder" | "file";
  children?: FileNode[];
}

const MOCK_FILES: FileNode[] = [
  { name: "src", type: "folder", children: [
    { name: "app", type: "folder", children: [
      { name: "layout.tsx", type: "file" },
      { name: "page.tsx", type: "file" },
      { name: "globals.css", type: "file" },
    ]},
    { name: "lib", type: "folder", children: [
      { name: "nexus-store.ts", type: "file" },
      { name: "nexus-api.ts", type: "file" },
    ]},
    { name: "components", type: "folder", children: [
      { name: "chat-panel.tsx", type: "file" },
      { name: "sidebar.tsx", type: "file" },
      { name: "code-panel.tsx", type: "file" },
      { name: "avatar-panel.tsx", type: "file" },
    ]},
  ]},
  { name: "public", type: "folder", children: [
    { name: "favicon.ico", type: "file" },
    { name: "logo.svg", type: "file" },
  ]},
  { name: "package.json", type: "file" },
  { name: "tsconfig.json", type: "file" },
  { name: "tailwind.config.ts", type: "file" },
];

const BUILD_MESSAGES = [
  "Compilation du code...",
  "Analyse des dépendances...",
  "Optimisation du bytecode...",
  "Exécution dans le sandbox...",
  "Collecte des résultats...",
];

const mockPreviewUrl = "http://localhost:3000";

function FileIcon({ name, isFolder }: { name: string; isFolder: boolean }) {
  if (isFolder) return <FolderClosed size={14} className="shrink-0 text-blue-400" />;
  const ext = name.split(".").pop();
  switch (ext) {
    case "tsx": case "ts": return <FileType size={14} className="shrink-0 text-blue-500" />;
    case "json": return <FileJson size={14} className="shrink-0 text-yellow-500" />;
    case "css": return <FileType size={14} className="shrink-0 text-pink-400" />;
    default: return <File size={14} className="shrink-0 text-muted-foreground" />;
  }
}

function FileTree({ nodes, depth = 0, expanded, onToggle, onSelect, selectedFile }: {
  nodes: FileNode[];
  depth?: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  selectedFile: string | null;
}) {
  return (
    <>
      {nodes.map((node) => {
        const path = `${node.name}`;
        const fullPath = `${depth ? `${selectedFile?.split("/").slice(0, depth).join("/")}/` : ""}${path}`;
        const isExpanded = expanded.has(path);
        return (
          <div key={path}>
            <button
              onClick={() => node.type === "folder" ? onToggle(path) : onSelect(path)}
              className={cn(
                "flex w-full items-center gap-1 px-2 py-0.5 text-xs transition-colors hover:bg-accent/30",
                selectedFile === path && !node.children ? "bg-accent/40 text-accent-foreground" : "text-muted-foreground",
              )}
              style={{ paddingLeft: `${12 + depth * 14}px` }}
            >
              {node.type === "folder" && (
                isExpanded ? <ChevronDown size={12} className="shrink-0" /> : <ChevronRight size={12} className="shrink-0" />
              )}
              <FileIcon name={node.name} isFolder={node.type === "folder"} />
              <span className="truncate">{node.name}</span>
            </button>
            {node.type === "folder" && isExpanded && node.children && (
              <FileTree
                nodes={node.children}
                depth={depth + 1}
                expanded={expanded}
                onToggle={(sub) => onToggle(`${path}/${sub}`)}
                onSelect={(sub) => onSelect(`${path}/${sub}`)}
                selectedFile={selectedFile}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

import { cn } from "@/lib/utils";



export function CodePanel() {
  const [code, setCode] = useState(`print("Bonjour depuis NEXUS!")`);
  const [language, setLanguage] = useState("python");
  const [sandboxed, setSandboxed] = useState(true);
  const [timeout, setTimeout_] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTerminal, setShowTerminal] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(mockPreviewUrl);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(["src", "src/app", "src/lib", "src/components", "public"]));
  const [selectedFile, setSelectedFile] = useState<string | null>("src/app/page.tsx");
  const [buildMsgIndex, setBuildMsgIndex] = useState(-1);
  const terminalRef = useRef<HTMLDivElement>(null);

  const toggleFolder = useCallback((path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!loading || buildMsgIndex >= BUILD_MESSAGES.length - 1) return;
    const t = setTimeout(() => setBuildMsgIndex((i) => i + 1), 400);
    return () => clearTimeout(t);
  }, [loading, buildMsgIndex]);

  useEffect(() => {
    if (!loading) setBuildMsgIndex(-1);
  }, [loading]);

  useEffect(() => {
    terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: "smooth" });
  }, [buildMsgIndex, result, error]);

  async function handleExecute() {
    setLoading(true);
    setResult(null);
    setError(null);
    setShowTerminal(true);
    try {
      const data = await api.executeCode(code, language, timeout, sandboxed);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de l'exécution");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border/60 bg-card px-3 py-2">
        <Terminal size={15} className="text-blue-400" />
        <h2 className="text-xs font-semibold tracking-wide text-foreground/80">Code Workspace</h2>
        <div className="ml-auto flex items-center gap-2">
          <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
            <SelectTrigger className="h-6 w-22 border-border/40 bg-muted text-[11px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-border/40 bg-muted text-xs">
              {LANGUAGES.map((l) => (
                <SelectItem key={l} value={l} className="text-xs">{l}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1.5">
            <Label className="text-[10px] text-muted-foreground">Sandbox</Label>
            <Switch checked={sandboxed} onCheckedChange={setSandboxed} className="scale-75" />
          </div>
          <Button
            onClick={handleExecute}
            disabled={loading || !code.trim()}
            size="sm"
            className="h-6 gap-1 px-2.5 text-[11px]"
          >
            {loading ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
            Exéc
          </Button>
        </div>
      </div>

      {/* Main 3-panel area */}
      <div className="flex flex-1 overflow-hidden">
        {/* File Explorer */}
        <div className="flex w-52 shrink-0 flex-col border-r border-border/60 bg-background">
          <div className="flex items-center gap-1.5 border-b border-border/60 px-3 py-1.5">
            <FolderClosed size={12} className="text-blue-400" />
            <span className="text-[10px] font-medium text-muted-foreground tracking-wide">EXPLORATEUR</span>
          </div>
          <ScrollArea className="flex-1">
            <div className="py-1">
              <FileTree
                nodes={MOCK_FILES}
                depth={0}
                expanded={expandedFolders}
                onToggle={toggleFolder}
                onSelect={setSelectedFile}
                selectedFile={selectedFile}
              />
            </div>
          </ScrollArea>
        </div>

        {/* Code Editor */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <Textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="flex-1 border-0 rounded-none bg-card p-4 font-mono text-sm leading-relaxed text-foreground/90 placeholder:text-muted-foreground/30 resize-none focus-visible:ring-0"
            placeholder="Écrivez votre code ici..."
          />
        </div>

        {/* Live Preview */}
        {showPreview && (
          <div className="flex w-72 shrink-0 flex-col border-l border-border/60 bg-background">
            <div className="flex items-center justify-between border-b border-border/60 px-3 py-1.5">
              <div className="flex items-center gap-1.5">
                <Monitor size={12} className="text-emerald-400" />
                <span className="text-[10px] font-medium text-muted-foreground tracking-wide">APERÇU EN DIRECT</span>
              </div>
              <button onClick={() => setShowPreview(false)} className="text-muted-foreground/50 hover:text-foreground">
                <X size={12} />
              </button>
            </div>
            <div className="flex-1 p-2">
              {previewUrl ? (
                <iframe
                  src={previewUrl}
                  className="h-full w-full rounded border border-border/40 bg-white"
                  title="Live Preview"
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <p className="text-[11px] text-muted-foreground/50">Aucun aperçu actif</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Terminal / Output */}
      <div className={cn("border-t border-border/60 transition-all", showTerminal ? "h-40" : "h-0 overflow-hidden")}>
        <div className="flex items-center justify-between border-b border-border/60 bg-background px-3 py-1">
          <div className="flex items-center gap-1.5">
            <Terminal size={12} className="text-emerald-400" />
            <span className="text-[10px] font-medium text-muted-foreground tracking-wide">TERMINAL</span>
            {loading && (
              <span className="ml-2 h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowPreview((p) => !p)}
              className="rounded p-0.5 text-muted-foreground/50 hover:text-foreground/70"
              title="Basculer l'aperçu"
            >
              <Monitor size={12} />
            </button>
            <button
              onClick={() => setShowTerminal(false)}
              className="rounded p-0.5 text-muted-foreground/50 hover:text-foreground/70"
              title="Fermer le terminal"
            >
              <Minimize2 size={12} />
            </button>
          </div>
        </div>
        <ScrollArea ref={terminalRef} className="h-[calc(10rem-2rem)]">
          <div className="p-3 font-mono text-xs leading-relaxed">
            {/* Building messages */}
            {loading && buildMsgIndex >= 0 && (
              <div className="space-y-0.5 mb-2">
                {BUILD_MESSAGES.slice(0, buildMsgIndex + 1).map((msg, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-muted-foreground/70">
                    <span className="inline-block h-3 w-1.5 animate-pulse bg-emerald-400/60" />
                    <span>{msg}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="mb-2 flex items-start gap-2">
                <Badge variant="destructive" className="mt-0.5 text-[9px] leading-none px-1 py-0">Erreur</Badge>
                <span className="text-red-400">{error}</span>
              </div>
            )}

            {/* Result */}
            {result && (
              <div className="space-y-1">
                {result.stdout && (
                  <pre className="text-emerald-400/90 whitespace-pre-wrap">{result.stdout}</pre>
                )}
                {result.stderr && (
                  <pre className="text-red-400/90 whitespace-pre-wrap">{result.stderr}</pre>
                )}
                <div className="flex items-center gap-3 pt-1.5 text-[10px] text-muted-foreground/60 border-t border-border/40 mt-1.5">
                  <span>code: {result.exit_code}</span>
                  <span>time: {result.execution_time_ms}ms</span>
                  {result.timed_out && <Badge variant="destructive" className="text-[9px] leading-none px-1 py-0">Timeout</Badge>}
                </div>
              </div>
            )}

            {/* Empty state */}
            {!result && !error && !loading && (
              <div className="text-muted-foreground/40 italic">
                <span className="text-emerald-400/50">$</span> En attente d'exécution...
              </div>
            )}

            {/* Always-blinking cursor */}
            <span className="inline-block h-4 w-2 ml-0.5 bg-foreground/40 animate-pulse align-middle" />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
