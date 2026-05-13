// ═══════════════════════════════════════════════════════════════
// NEXUS — Artifact Renderer
// When the agent creates an artifact (HTML page, chart, image, code),
// it renders inline in the chat or expands into a side panel.
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useNexusStore } from "@/lib/nexus-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  X, Copy, ExternalLink, Code2, Globe, Image as ImageIcon,
  FileText, BarChart3, Check, Maximize2, Minimize2,
} from "lucide-react";
import type { Artifact, ArtifactType } from "@/types/nexus";

// ── Artifact Type Icons & Colors ─────────────────────────────

const ARTIFACT_META: Record<ArtifactType, { icon: React.ReactNode; color: string; label: string }> = {
  html: { icon: <Globe size={14} />, color: "text-orange-400", label: "HTML" },
  code: { icon: <Code2 size={14} />, color: "text-cyan-400", label: "Code" },
  image: { icon: <ImageIcon size={14} />, color: "text-pink-400", label: "Image" },
  chart: { icon: <BarChart3 size={14} />, color: "text-emerald-400", label: "Chart" },
  document: { icon: <FileText size={14} />, color: "text-violet-400", label: "Document" },
  iframe: { icon: <Globe size={14} />, color: "text-sky-400", label: "Preview" },
};

// ── Detect language from artifact ────────────────────────────

function artifactLanguage(artifact: Artifact): string {
  if (artifact.language) return artifact.language;
  if (artifact.type === "html") return "html";
  if (artifact.type === "code") return "typescript";
  if (artifact.type === "document") return "markdown";
  return "text";
}

// ── HTML Renderer (sandboxed iframe) ────────────────────────

function HtmlRenderer({ content }: { content: string }) {
  const sandboxAttrs = "allow-scripts allow-same-origin";
  return (
    <iframe
      srcDoc={content}
      sandbox={sandboxAttrs}
      className="w-full h-full border-0 bg-white rounded-lg"
      title="Artifact Preview"
    />
  );
}

// ── Code Renderer (syntax highlighted) ──────────────────────

function CodeRenderer({ content, language }: { content: string; language: string }) {
  return (
    <ScrollArea className="h-full">
      <div className="p-4">
        <SyntaxHighlighter
          language={language}
          style={oneDark}
          PreTag="div"
          showLineNumbers
          customStyle={{
            margin: 0,
            borderRadius: "0.5rem",
            fontSize: "0.75rem",
            lineHeight: "1.5rem",
            background: "transparent",
          }}
        >
          {content}
        </SyntaxHighlighter>
      </div>
    </ScrollArea>
  );
}

// ── Image Renderer ──────────────────────────────────────────

function ImageRenderer({ content }: { content: string }) {
  // content could be base64 data URI or a regular URL
  const src = content.startsWith("data:") || content.startsWith("http")
    ? content
    : `data:image/png;base64,${content}`;

  return (
    <div className="flex items-center justify-center h-full p-4">
      <img
        src={src}
        alt="Artifact"
        className="max-w-full max-h-full object-contain rounded-lg shadow-lg"
      />
    </div>
  );
}

// ── Chart Renderer (simple SVG fallback) ─────────────────────

function ChartRenderer({ content }: { content: string }) {
  // If the content is SVG, render it directly
  if (content.trim().startsWith("<svg") || content.trim().startsWith("<?xml")) {
    return (
      <div
        className="flex items-center justify-center h-full p-4"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }

  // If it's HTML (canvas-based chart), use iframe
  if (content.trim().startsWith("<!") || content.trim().startsWith("<html") || content.includes("<canvas")) {
    return <HtmlRenderer content={content} />;
  }

  // Fallback: show as code
  return <CodeRenderer content={content} language="json" />;
}

// ── Document Renderer (formatted text) ──────────────────────

function DocumentRenderer({ content }: { content: string }) {
  return (
    <ScrollArea className="h-full">
      <div className="prose prose-sm dark:prose-invert max-w-none p-4">
        <pre className="whitespace-pre-wrap font-sans text-sm text-foreground/80">{content}</pre>
      </div>
    </ScrollArea>
  );
}

// ── Artifact Content Router ─────────────────────────────────

function ArtifactContent({ artifact, expanded }: { artifact: Artifact; expanded: boolean }) {
  const heightClass = expanded ? "h-full" : "h-64";

  switch (artifact.type) {
    case "html":
    case "iframe":
      return (
        <div className={heightClass}>
          <HtmlRenderer content={artifact.content} />
        </div>
      );
    case "code":
      return (
        <div className={heightClass}>
          <CodeRenderer content={artifact.content} language={artifactLanguage(artifact)} />
        </div>
      );
    case "image":
      return (
        <div className={heightClass}>
          <ImageRenderer content={artifact.content} />
        </div>
      );
    case "chart":
      return (
        <div className={heightClass}>
          <ChartRenderer content={artifact.content} />
        </div>
      );
    case "document":
      return (
        <div className={heightClass}>
          <DocumentRenderer content={artifact.content} />
        </div>
      );
    default:
      return (
        <div className={`${heightClass} flex items-center justify-center text-muted-foreground`}>
          Unsupported artifact type
        </div>
      );
  }
}

// ── ArtifactCard (embedded in chat) ─────────────────────────

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const { setActiveArtifact } = useNexusStore();
  const [copied, setCopied] = useState(false);
  const meta = ARTIFACT_META[artifact.type] || ARTIFACT_META.code;

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(artifact.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [artifact.content]);

  // Build a small preview thumbnail
  const thumbnail = useMemo(() => {
    switch (artifact.type) {
      case "html":
      case "iframe":
        return (
          <div className="w-full h-20 bg-white/5 rounded-md overflow-hidden relative">
            <div className="absolute inset-0 flex items-center justify-center">
              <Globe size={20} className="text-orange-400/40" />
            </div>
            <iframe
              srcDoc={artifact.content}
              className="w-[400%] h-[400%] origin-top-left scale-[0.25] pointer-events-none"
              title="Preview"
            />
          </div>
        );
      case "code":
        return (
          <div className="w-full h-20 bg-[#1a1a2e]/50 rounded-md p-2 overflow-hidden">
            <pre className="text-[7px] font-mono text-foreground/30 leading-tight line-clamp-4">
              {artifact.content.slice(0, 200)}
            </pre>
          </div>
        );
      case "image": {
        const imgSrc = artifact.content.startsWith("data:") || artifact.content.startsWith("http")
          ? artifact.content
          : `data:image/png;base64,${artifact.content.slice(0, 200)}`;
        return (
          <div className="w-full h-20 rounded-md overflow-hidden bg-muted/10">
            <img src={imgSrc} alt="" className="w-full h-full object-cover opacity-70" />
          </div>
        );
      }
      case "chart":
        return (
          <div className="w-full h-20 bg-emerald-500/5 rounded-md flex items-center justify-center">
            <BarChart3 size={24} className="text-emerald-400/40" />
          </div>
        );
      default:
        return (
          <div className="w-full h-20 bg-muted/5 rounded-md flex items-center justify-center">
            <FileText size={20} className="text-muted-foreground/30" />
          </div>
        );
    }
  }, [artifact]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="rounded-xl border border-border/20 bg-muted/10 overflow-hidden w-64"
    >
      {/* Thumbnail */}
      <div className="px-3 pt-3">
        {thumbnail}
      </div>

      {/* Info + Actions */}
      <div className="px-3 py-2.5 space-y-2">
        <div className="flex items-center gap-2">
          <span className={meta.color}>{meta.icon}</span>
          <span className="text-[11px] font-medium text-foreground/80 truncate flex-1">
            {artifact.title}
          </span>
          <span className="text-[8px] px-1.5 py-0.5 rounded bg-muted/20 text-muted-foreground">
            {meta.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[10px] gap-1 text-primary hover:text-primary/80"
            onClick={() => setActiveArtifact(artifact.id)}
          >
            <Maximize2 size={10} />
            Open
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[10px] gap-1 text-muted-foreground hover:text-foreground/80"
            onClick={handleCopy}
          >
            {copied ? <Check size={10} className="text-emerald-500" /> : <Copy size={10} />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

// ── ArtifactPanel (slides in from right) ────────────────────

export function ArtifactPanel() {
  const { artifacts, activeArtifactId, setActiveArtifact } = useNexusStore();
  const [isFullscreen, setIsFullscreen] = useState(false);

  const activeArtifact = useMemo(
    () => artifacts.find((a) => a.id === activeArtifactId) ?? null,
    [artifacts, activeArtifactId]
  );

  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!activeArtifact) return;
    navigator.clipboard.writeText(activeArtifact.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [activeArtifact]);

  if (!activeArtifact) return null;

  const meta = ARTIFACT_META[activeArtifact.type] || ARTIFACT_META.code;

  return (
    <AnimatePresence>
      <motion.div
        key="artifact-panel"
        initial={{ x: "100%", opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: "100%", opacity: 0 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className={`fixed top-0 right-0 z-50 h-full bg-background border-l border-border/20 shadow-2xl flex flex-col ${
          isFullscreen ? "w-full" : "w-[480px]"
        }`}
      >
        {/* Header */}
        <div className="shrink-0 flex items-center gap-3 px-4 py-3 border-b border-border/15 bg-muted/5">
          <span className={meta.color}>{meta.icon}</span>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-foreground/90 truncate">
              {activeArtifact.title}
            </h3>
            <span className="text-[9px] text-muted-foreground">{meta.label} artifact</span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setIsFullscreen(!isFullscreen)}
              title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
            >
              {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={handleCopy}
              title="Copy content"
            >
              {copied ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
              onClick={() => setActiveArtifact(null)}
              title="Close"
            >
              <X size={14} />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ArtifactContent artifact={activeArtifact} expanded />
        </div>

        {/* Footer with meta */}
        <div className="shrink-0 px-4 py-2 border-t border-border/10 flex items-center justify-between">
          <span className="text-[9px] text-muted-foreground/50 font-mono">
            {new Date(activeArtifact.createdAt).toLocaleTimeString()}
          </span>
          <span className="text-[9px] text-muted-foreground/50 font-mono">
            {activeArtifact.content.length.toLocaleString()} chars
          </span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
