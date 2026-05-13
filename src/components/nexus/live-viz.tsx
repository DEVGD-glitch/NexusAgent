// ═══════════════════════════════════════════════════════════════
// NEXUS — Live Visualization (Brick-by-Brick Build View)
// Like z.ai agent mode: file tree + code preview + diffs + progress
// Every file creation plays out line-by-line in real time
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useNexusStore } from "@/lib/nexus-store";
import {
  Folder, FolderOpen, File, ChevronRight, ChevronDown,
  Check, Loader2, X, Play, AlertCircle,
  FileCode2, FileJson, FileText, Image as ImageIcon,
  FolderPlus, FilePlus, Pencil, Trash2,
  Terminal, Package, Rocket, GitBranch,
} from "lucide-react";
import type { VizEvent, FileTreeNode } from "@/types/nexus";

// ── Helpers ──────────────────────────────────────────────────

const FILE_TYPE_COLORS: Record<string, string> = {
  ts: "text-blue-400",
  tsx: "text-blue-400",
  js: "text-yellow-300",
  jsx: "text-yellow-300",
  py: "text-green-400",
  json: "text-amber-400",
  css: "text-pink-400",
  scss: "text-pink-400",
  html: "text-orange-400",
  md: "text-gray-400",
  yml: "text-red-400",
  yaml: "text-red-400",
  toml: "text-red-400",
  rs: "text-orange-500",
  go: "text-cyan-400",
  sql: "text-emerald-300",
  sh: "text-lime-400",
  env: "text-purple-400",
  prisma: "text-teal-400",
};

function getFileExtension(name: string): string {
  const parts = name.split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

function getFileColor(name: string): string {
  const ext = getFileExtension(name);
  return FILE_TYPE_COLORS[ext] || "text-muted-foreground";
}

function getFileIcon(name: string) {
  const ext = getFileExtension(name);
  switch (ext) {
    case "ts": case "tsx": case "js": case "jsx": return <FileCode2 size={14} />;
    case "json": return <FileJson size={14} />;
    case "md": case "txt": return <FileText size={14} />;
    case "png": case "jpg": case "svg": case "gif": return <ImageIcon size={14} />;
    default: return <File size={14} />;
  }
}

function detectLanguage(path?: string): string {
  if (!path) return "text";
  const ext = getFileExtension(path);
  const map: Record<string, string> = {
    ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
    py: "python", json: "json", css: "css", scss: "scss",
    html: "html", md: "markdown", yml: "yaml", yaml: "yaml",
    rs: "rust", go: "go", sql: "sql", sh: "bash", toml: "toml",
    prisma: "prisma",
  };
  return map[ext] || "text";
}

// ── FileTree Component ───────────────────────────────────────

function FileTreeItem({
  node,
  depth,
  selectedPath,
  onSelect,
  newFiles,
  modifiedFiles,
}: {
  node: FileTreeNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  newFiles: Set<string>;
  modifiedFiles: Set<string>;
}) {
  const [expanded, setExpanded] = useState(true);
  const isDir = node.type === "directory";
  const isSelected = node.path === selectedPath;
  const isNew = newFiles.has(node.path);
  const isModified = modifiedFiles.has(node.path);

  return (
    <div>
      <motion.div
        initial={isNew ? { opacity: 0, x: -10 } : false}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2 }}
        className={`flex items-center gap-1 py-1 px-2 rounded-md cursor-pointer text-xs group
          ${isSelected ? "bg-primary/15 text-primary" : "hover:bg-muted/30 text-foreground/70"}
          ${isNew ? "ring-1 ring-emerald-500/40" : ""}
          ${isModified ? "ring-1 ring-amber-500/40" : ""}
        `}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => {
          if (isDir) setExpanded(!expanded);
          else onSelect(node.path);
        }}
      >
        {isDir ? (
          <>
            <motion.span
              animate={{ rotate: expanded ? 90 : 0 }}
              transition={{ duration: 0.15 }}
              className="shrink-0"
            >
              <ChevronRight size={10} className="text-muted-foreground" />
            </motion.span>
            {expanded ? (
              <FolderOpen size={14} className="text-amber-400 shrink-0" />
            ) : (
              <Folder size={14} className="text-amber-400/70 shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-[10px] shrink-0" />
            <span className={`shrink-0 ${getFileColor(node.name)}`}>
              {getFileIcon(node.name)}
            </span>
          </>
        )}
        <span className="truncate flex-1 ml-1">{node.name}</span>
        {isNew && (
          <motion.span
            animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"
          />
        )}
        {isModified && !isNew && (
          <motion.span
            animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"
          />
        )}
      </motion.div>
      <AnimatePresence>
        {isDir && expanded && node.children && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            {node.children.map((child) => (
              <FileTreeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                onSelect={onSelect}
                newFiles={newFiles}
                modifiedFiles={modifiedFiles}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function FileTree({
  tree,
  selectedPath,
  onSelect,
  newFiles,
  modifiedFiles,
}: {
  tree: FileTreeNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
  newFiles: Set<string>;
  modifiedFiles: Set<string>;
}) {
  if (tree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground/40 py-8">
        <FolderPlus size={24} className="mb-2" />
        <span className="text-[10px]">No files yet</span>
      </div>
    );
  }

  return (
    <div className="py-2 space-y-0">
      {tree.map((node) => (
        <FileTreeItem
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          onSelect={onSelect}
          newFiles={newFiles}
          modifiedFiles={modifiedFiles}
        />
      ))}
    </div>
  );
}

// ── CodePreview Component ────────────────────────────────────

export function CodePreview({
  content,
  language,
  visibleLines,
  isStreaming,
}: {
  content: string;
  language: string;
  visibleLines: number;
  isStreaming: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const lines = content.split("\n");
  const displayedLines = lines.slice(0, visibleLines);

  // Auto-scroll to bottom as lines come in
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [visibleLines]);

  if (!content) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground/30 py-12">
        <FileCode2 size={28} className="mb-2" />
        <span className="text-[10px]">Select a file to preview</span>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto font-mono text-[11px] leading-5">
      {/* Line numbers + code */}
      <div className="flex">
        {/* Line numbers */}
        <div className="shrink-0 text-right pr-3 pl-2 select-none text-muted-foreground/30 border-r border-border/10">
          {displayedLines.map((_, i) => (
            <div key={i} className="h-5">
              {i + 1}
            </div>
          ))}
        </div>
        {/* Code content */}
        <div className="flex-1 overflow-x-auto">
          <SyntaxHighlighter
            language={language}
            style={oneDark}
            PreTag="div"
            customStyle={{
              margin: 0,
              padding: "0 0.75rem",
              background: "transparent",
              fontSize: "0.6875rem",
              lineHeight: "1.25rem",
            }}
            codeTagProps={{
              style: { fontFamily: "inherit" },
            }}
            showLineNumbers={false}
            wrapLines
          >
            {displayedLines.join("\n")}
          </SyntaxHighlighter>
          {/* Blinking cursor on the current line */}
          {isStreaming && (
            <motion.div
              className="flex items-center h-5 ml-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.span
                className="inline-block w-[7px] h-[14px] bg-primary/80 rounded-[1px]"
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── DiffViewer Component ─────────────────────────────────────

export function DiffViewer({ diff }: { diff: { old: string; new: string } }) {
  const oldLines = diff.old.split("\n");
  const newLines = diff.new.split("\n");
  const maxLen = Math.max(oldLines.length, newLines.length);

  return (
    <div className="flex h-full overflow-hidden text-[11px] font-mono">
      {/* Old (left) */}
      <div className="flex-1 overflow-y-auto border-r border-border/10">
        <div className="px-2 py-1.5 text-[9px] font-semibold text-red-400 bg-red-500/5 border-b border-red-500/10 sticky top-0">
          Original
        </div>
        {Array.from({ length: maxLen }).map((_, i) => {
          const line = oldLines[i];
          const isNewInNew = line !== undefined && !newLines.includes(line);
          const isRemoved = line !== undefined && newLines[i] !== line;
          return (
            <div
              key={`old-${i}`}
              className={`flex px-2 h-5 items-center ${
                isRemoved ? "bg-red-500/10 text-red-300" : "text-foreground/60"
              }`}
            >
              <span className="w-6 text-right pr-2 text-muted-foreground/20 select-none">{i + 1}</span>
              {isRemoved && <span className="text-red-400 mr-1">-</span>}
              <span className="truncate">{line ?? ""}</span>
            </div>
          );
        })}
      </div>
      {/* New (right) */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-2 py-1.5 text-[9px] font-semibold text-emerald-400 bg-emerald-500/5 border-b border-emerald-500/10 sticky top-0">
          Modified
        </div>
        {Array.from({ length: maxLen }).map((_, i) => {
          const line = newLines[i];
          const isAdded = line !== undefined && oldLines[i] !== line;
          return (
            <div
              key={`new-${i}`}
              className={`flex px-2 h-5 items-center ${
                isAdded ? "bg-emerald-500/10 text-emerald-300" : "text-foreground/60"
              }`}
            >
              <span className="w-6 text-right pr-2 text-muted-foreground/20 select-none">{i + 1}</span>
              {isAdded && <span className="text-emerald-400 mr-1">+</span>}
              <span className="truncate">{line ?? ""}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── BuildProgress Component ──────────────────────────────────

export function BuildProgress({ events }: { events: VizEvent[] }) {
  const buildSteps = useMemo(() => {
    return events
      .filter((e) =>
        ["viz_build_step", "viz_file_create", "viz_file_edit", "viz_code_write",
         "viz_dependency_install", "viz_command_run", "viz_test_run", "viz_build_complete",
         "viz_error"].includes(e.type)
      );
  }, [events]);

  const completedCount = buildSteps.filter((s) => s.status === "completed").length;
  const runningStep = buildSteps.find((s) => s.status === "running");
  const errorStep = buildSteps.find((s) => s.status === "error");
  const totalSteps = buildSteps.length;
  const progressPercent = totalSteps > 0 ? Math.round((completedCount / totalSteps) * 100) : 0;
  const isComplete = buildSteps.some((e) => e.type === "viz_build_complete" && e.status === "completed");

  const STEP_ICONS: Record<string, React.ReactNode> = {
    viz_file_create: <FilePlus size={11} className="text-blue-400" />,
    viz_file_edit: <Pencil size={11} className="text-amber-400" />,
    viz_code_write: <FileCode2 size={11} className="text-cyan-400" />,
    viz_dependency_install: <Package size={11} className="text-purple-400" />,
    viz_command_run: <Terminal size={11} className="text-lime-400" />,
    viz_test_run: <Play size={11} className="text-teal-400" />,
    viz_build_step: <GitBranch size={11} className="text-sky-400" />,
    viz_build_complete: <Rocket size={11} className="text-emerald-400" />,
    viz_error: <AlertCircle size={11} className="text-red-400" />,
  };

  return (
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-medium text-foreground/60">
            {isComplete ? "Build Complete" : runningStep ? runningStep.title : "Building..."}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground">{progressPercent}%</span>
        </div>
        <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full ${
              errorStep ? "bg-red-500" : isComplete ? "bg-emerald-500" : "bg-cyan-500"
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Step list */}
      <div className="space-y-1 max-h-36 overflow-y-auto">
        {buildSteps.map((step) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.15 }}
            className={`flex items-center gap-2 px-2 py-1 rounded-md text-[10px] ${
              step.status === "running" ? "bg-cyan-500/10 border border-cyan-500/20" :
              step.status === "error" ? "bg-red-500/10" :
              step.status === "completed" ? "bg-muted/5" : "bg-muted/5 opacity-50"
            }`}
          >
            <span className="shrink-0">
              {STEP_ICONS[step.type] || <GitBranch size={11} className="text-muted-foreground" />}
            </span>
            <span className="flex-1 truncate text-foreground/70">{step.title}</span>
            {step.status === "completed" && <Check size={10} className="text-emerald-500 shrink-0" />}
            {step.status === "running" && <Loader2 size={10} className="text-cyan-400 animate-spin shrink-0" />}
            {step.status === "error" && <X size={10} className="text-red-500 shrink-0" />}
            {step.status === "pending" && <span className="w-2.5 h-2.5 rounded-full border border-muted-foreground/20 shrink-0" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ── LiveVizPanel (Main Orchestrator) ─────────────────────────

export function LiveVizPanel() {
  const { vizEvents, fileTree } = useNexusStore();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"code" | "diff">("code");

  // Track which files are new / modified based on viz events
  const newFiles = useMemo(() => {
    const set = new Set<string>();
    vizEvents.forEach((e) => {
      if (e.type === "viz_file_create" && e.path) set.add(e.path);
    });
    return set;
  }, [vizEvents]);

  const modifiedFiles = useMemo(() => {
    const set = new Set<string>();
    vizEvents.forEach((e) => {
      if (e.type === "viz_file_edit" && e.path) set.add(e.path);
    });
    return set;
  }, [vizEvents]);

  // Track code content per file and visible line count
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [visibleLineCounts, setVisibleLineCounts] = useState<Record<string, number>>({});
  const [currentDiff, setCurrentDiff] = useState<{ old: string; new: string } | null>(null);

  // Process viz events to build up file contents incrementally
  useEffect(() => {
    vizEvents.forEach((event) => {
      if (event.type === "viz_file_create" && event.path && event.content) {
        setFileContents((prev) => ({ ...prev, [event.path!]: event.content! }));
        setVisibleLineCounts((prev) => ({ ...prev, [event.path!]: event.content!.split("\n").length }));
        if (!selectedPath) setSelectedPath(event.path);
      }

      if (event.type === "viz_code_write" && event.path && event.content) {
        setFileContents((prev) => {
          const existing = prev[event.path!] || "";
          const updated = existing + (existing ? "\n" : "") + event.content!;
          return { ...prev, [event.path!]: updated };
        });
        // Animate line reveal: gradually increase visible lines
        if (event.line_number !== undefined && event.total_lines !== undefined) {
          setVisibleLineCounts((prev) => ({
            ...prev,
            [event.path!]: event.line_number!,
          }));
        } else {
          // Fallback: show all lines immediately
          setVisibleLineCounts((prev) => {
            const content = fileContents[event.path!] || "";
            return { ...prev, [event.path!]: content.split("\n").length };
          });
        }
        if (!selectedPath) setSelectedPath(event.path);
      }

      if (event.type === "viz_file_edit" && event.diff) {
        setCurrentDiff(event.diff);
        setViewMode("diff");
        if (event.path) setSelectedPath(event.path);
      }

      if (event.type === "viz_diff_preview" && event.diff) {
        setCurrentDiff(event.diff);
        setViewMode("diff");
      }
    });
  }, [vizEvents]);

  // Compute effective view mode: if selectedPath has no diff, force code mode
  const hasDiffForSelected = useMemo(() => {
    if (!selectedPath) return false;
    return vizEvents.some(
      (e) => (e.type === "viz_file_edit" || e.type === "viz_diff_preview") && e.path === selectedPath && e.diff
    );
  }, [selectedPath, vizEvents]);

  const effectiveViewMode = hasDiffForSelected ? viewMode : "code";
  const effectiveDiff = hasDiffForSelected ? currentDiff : null;

  const activeContent = selectedPath ? fileContents[selectedPath] || "" : "";
  const activeVisibleLines = selectedPath ? visibleLineCounts[selectedPath] || 0 : 0;
  const activeLang = detectLanguage(selectedPath ?? undefined);
  const isStreamingCode = vizEvents.some(
    (e) => e.type === "viz_code_write" && e.path === selectedPath && e.status === "running"
  );

  // Count files in the tree
  const fileCount = useMemo(() => {
    function count(nodes: FileTreeNode[]): number {
      return nodes.reduce((acc, n) => acc + (n.type === "file" ? 1 : 0) + count(n.children || []), 0);
    }
    return count(fileTree);
  }, [fileTree]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="h-full flex flex-col bg-background border border-border/15 rounded-xl overflow-hidden"
    >
      {/* Header with progress */}
      <div className="shrink-0 border-b border-border/15 px-4 py-3 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
            <span className="text-xs font-semibold text-foreground/80">Live Build</span>
            <span className="text-[9px] text-muted-foreground font-mono">
              {fileCount} file{fileCount !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setViewMode("code")}
              className={`px-2 py-0.5 rounded text-[9px] transition-colors ${
                effectiveViewMode === "code"
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground/70"
              }`}
            >
              Code
            </button>
            <button
              onClick={() => setViewMode("diff")}
              className={`px-2 py-0.5 rounded text-[9px] transition-colors ${
                effectiveViewMode === "diff"
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground/70"
              }`}
            >
              Diff
            </button>
          </div>
        </div>
        <BuildProgress events={vizEvents} />
      </div>

      {/* Split view: FileTree | Code/Diff preview */}
      <div className="flex-1 flex min-h-0">
        {/* Left: File tree */}
        <div className="w-56 shrink-0 border-r border-border/10 overflow-y-auto bg-muted/5">
          <FileTree
            tree={fileTree}
            selectedPath={selectedPath}
            onSelect={(path) => {
              setSelectedPath(path);
              if (!vizEvents.some((e) => (e.type === "viz_file_edit" || e.type === "viz_diff_preview") && e.path === path && e.diff)) {
                setViewMode("code");
              }
            }}
            newFiles={newFiles}
            modifiedFiles={modifiedFiles}
          />
        </div>

        {/* Right: Code preview or diff */}
        <div className="flex-1 min-w-0 bg-[#1a1a2e]/40">
          {effectiveViewMode === "diff" && effectiveDiff ? (
            <DiffViewer diff={effectiveDiff} />
          ) : (
            <CodePreview
              content={activeContent}
              language={activeLang}
              visibleLines={activeVisibleLines}
              isStreaming={isStreamingCode}
            />
          )}
        </div>
      </div>
    </motion.div>
  );
}
