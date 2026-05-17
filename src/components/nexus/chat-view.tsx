// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat View (THE Central Hub) — V3 Enhanced
// Like Cursor/Windsurf: ONE conversation, everything in chat
// Generative UI: memory cards, code results, web results, build steps
// all render AS PART OF the conversation
// V3: VoiceButton, LiveVizPanel, ArtifactPanel, Stop button,
//     conversation persistence, streaming token accumulation
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import dynamic from "next/dynamic";

const VRMAvatar = dynamic(() => import("./vrm-avatar").then((m) => m.VRMAvatar), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-16 h-16 rounded-full border-2 border-cyan-500/30 border-t-cyan-400 animate-spin" />
    </div>
  ),
});
import {
  AgentActivityCard, BuildStepsCard,
} from "./gen-ui";
import { A2UIRenderer } from "./a2ui-renderer";
import { VoiceButton } from "./voice-ui";
import { VRMHubModal } from "./vrm-hub";
import { ChatBubble } from "./chat-bubble";
import { ThinkingPanel } from "./thinking-panel";
import { ApprovalCard } from "./approval-card";
import { StreamingContent } from "./streaming-content";
import { motion } from "framer-motion";
import {
  Send, Sparkles, Shield, Zap, Settings,
  Square, X, FileCode, BarChart3, Image as ImageIcon, FileText, Code2,
  Eye, Volume2, VolumeX, User, Menu,
} from "lucide-react";
import { ConversationSidebar } from "./conversation-sidebar";
import type { VizEvent, Artifact } from "@/types/nexus";
import { createLogger } from "@/lib/logger";
import { useIsMobile } from "@/hooks/use-mobile";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

const log = createLogger("ChatView");

// ── Constants ────────────────────────────────────────────────
const STORAGE_KEY = "nexus_conversations";

// ── Live Viz Panel ──────────────────────────────────────────
// Shows real-time visualization events to the right of chat

function LiveVizPanel({ events, onClose }: { events: VizEvent[]; onClose: () => void }) {
  const statusColor: Record<string, string> = {
    pending: "text-amber-400",
    running: "text-cyan-400",
    completed: "text-emerald-400",
    error: "text-red-400",
  };

  const statusBg: Record<string, string> = {
    pending: "bg-amber-500/5",
    running: "bg-cyan-500/5",
    completed: "bg-emerald-500/5",
    error: "bg-red-500/5",
  };

  return (
    <div className="h-full flex flex-col bg-background/80 border-l border-border/15">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/10 shrink-0">
        <div className="flex items-center gap-2">
          <Eye size={12} className="text-cyan-400" />
          <span className="text-[11px] font-medium text-foreground/70">Visualisation en direct</span>
          <Badge variant="outline" className="text-[8px] h-4">{events.length}</Badge>
        </div>
        <button
          onClick={onClose}
          aria-label="Fermer la visualisation"
          className="w-5 h-5 rounded hover:bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={10} />
        </button>
      </div>

      {/* Events list */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1" role="status" aria-live="polite" aria-atomic="false">
          {events.slice(-50).map((ev, i) => (
            <motion.div
              key={ev.id || i}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.15, delay: i === events.slice(-50).length - 1 ? 0.05 : 0 }}
              className={`rounded-lg border border-border/10 p-2 ${statusBg[ev.status] || ""}`}
            >
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  ev.status === "running" ? "bg-cyan-500 animate-pulse" :
                  ev.status === "completed" ? "bg-emerald-500" :
                  ev.status === "error" ? "bg-red-500" : "bg-amber-500"
                }`} />
                <span className="text-[10px] font-medium text-foreground/80 truncate flex-1">{ev.title}</span>
              </div>
              {ev.detail && (
                <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-2 pl-3.5">{ev.detail}</p>
              )}
              {ev.progress > 0 && ev.progress < 100 && (
                <Progress value={ev.progress} className="h-1 mt-1" />
              )}
              {ev.path && (
                <p className="text-[8px] text-muted-foreground/60 font-mono mt-0.5 pl-3.5 truncate">{ev.path}</p>
              )}
            </motion.div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

// ── Artifact Panel ──────────────────────────────────────────
// Renders artifacts (HTML, charts, images, documents, code)

function ArtifactPanel({ artifact, onClose }: { artifact: Artifact; onClose: () => void }) {
  const iconMap: Record<string, React.ReactNode> = {
    html: <FileCode size={12} className="text-orange-400" />,
    chart: <BarChart3 size={12} className="text-cyan-400" />,
    image: <ImageIcon size={12} className="text-violet-400" />,
    document: <FileText size={12} className="text-teal-400" />,
    code: <Code2 size={12} className="text-amber-400" />,
    iframe: <FileCode size={12} className="text-blue-400" />,
  };

  return (
    <div className="h-full flex flex-col bg-background/80 border-l border-border/15">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/10 shrink-0">
        <div className="flex items-center gap-2">
          {iconMap[artifact.type] || <FileCode size={12} />}
          <span className="text-[11px] font-medium text-foreground/70">{artifact.title}</span>
          <Badge variant="outline" className="text-[8px] h-4">{artifact.type}</Badge>
        </div>
        <button
          onClick={onClose}
          aria-label="Fermer l'artefact"
          className="w-5 h-5 rounded hover:bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={10} />
        </button>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-3">
          {artifact.type === "html" || artifact.type === "iframe" ? (
            <iframe
              srcDoc={artifact.content}
              className="w-full min-h-[300px] border-0 rounded-lg bg-white"
              sandbox="allow-scripts"
              title={artifact.title}
            />
          ) : artifact.type === "code" ? (
            <SyntaxHighlighter
              style={oneDark}
              language={artifact.language || "typescript"}
              PreTag="div"
              customStyle={{ fontSize: "0.78rem", borderRadius: "0.5rem", margin: 0 }}
            >
              {artifact.content}
            </SyntaxHighlighter>
          ) : artifact.type === "image" ? (
            <img
              src={artifact.content.startsWith("data:") ? artifact.content : `data:image/png;base64,${artifact.content}`}
              alt={artifact.title}
              className="max-w-full rounded-lg"
            />
          ) : (
            <pre className="text-[11px] font-mono whitespace-pre-wrap text-foreground/80">{artifact.content}</pre>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ── Main Chat View ──────────────────────────────────────────

export function ChatView() {
  const {
    conversations, activeConversationId, addConversation,
    addMessage, provider, model,
    agentStatus, setAgentStatus, addActivity, clearActivity,
    avatarExpression, avatarEnabled, avatarModelUrl, setAvatarModelUrl,
    vrmHubOpen, setVrmHubOpen,
    agentMode, setAgentMode,
    agentActivity, buildSteps, clearBuildSteps,
    backendConnected,
    vizEvents, clearVizEvents,
    artifacts, activeArtifactId, setActiveArtifact,
    voiceState, voiceConfig,
    pendingApprovals, removeApprovalRequest,
    a2uiCards,
    settingsOpen, setSettingsOpen,
  } = useNexusStore();

  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [showVizPanel, setShowVizPanel] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const streamTokenBufferRef = useRef<string>("");
  const streamTokenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Professional mode from store (hologram instead of VRM for professional setting)
  const avatarProfessionalMode = useNexusStore((state) => state.avatarProfessionalMode);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConv?.messages ?? [];
  const isWorking = agentStatus !== "idle";

  // Active artifact
  const activeArtifact = artifacts.find((a) => a.id === activeArtifactId);

  // ── Conversation Persistence ──────────────────────────────────

  // Save conversations to localStorage on every change
  useEffect(() => {
    if (conversations.length > 0) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
          conversations,
          activeConversationId,
        }));
      } catch (error) { log.warn('localStorage save failed', error); }
    }
  }, [conversations, activeConversationId]);

  // Load conversations from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const { conversations: savedConvs, activeConversationId: savedActiveId } = JSON.parse(saved);
        if (savedConvs && savedConvs.length > 0) {
          // Use the store's internal state to restore
          const store = useNexusStore.getState();
          // Only restore if store is empty (first load)
          if (store.conversations.length === 0) {
            useNexusStore.setState({
              conversations: savedConvs,
              activeConversationId: savedActiveId,
            });
          }
        }
      }
    } catch (error) { log.warn('localStorage load failed', error); }
  }, []);

  // Initialize first conversation if none exists - Enhanced Onboarding
  useEffect(() => {
    if (!activeConversationId) {
      const id = addConversation();
      addMessage(id, {
        role: "assistant",
        content: `# 👋 Bienvenue sur **NEXUS** — Votre Agent IA Souverain

Je suis un agent IA complet qui fonctionne **localement**, sans dépendance cloud obligatoire.

## 🚀 Ce que je peux faire :

- 🔍 Recherche web — Trouver des informations à jour
- 💻 Exécution de code — Tester, déboguer, construire
- 🧠 Mémoire 5 couches — Se souvenir de nos conversations
- 📊 Analyse de données — PDF, Excel, documents
- 🎨 Génération d'images — Créer des visuels
- 🤖 Multi-agents — Coordonner des tâches complexes

## 💡 Suggestions pour commencer :

- "Recherche les dernières nouvelles sur l'IA générative"
- "Crée une application React avec TailwindCSS"
- "Analyse ce document PDF et résume-le"
- "Génère une image de paysage futuriste"

## ⚙️ Personnalisation :

- **⌘K** — Palette de commandes rapides
- **⌘,** — Paramètres et configuration
- **Avatar** — Cliquez sur "Choisir avatar" pour personnaliser
- **Mode Pro** — Désactivez l'avatar dans les paramètres pour un environnement professionnel

**Dites-moi ce dont vous avez besoin !**`,
      });
    }
  }, [activeConversationId, addConversation, addMessage]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    }
  }, [messages, agentActivity, streamingContent, buildSteps]);

  // Auto-show viz panel when events arrive
  useEffect(() => {
    if (vizEvents.length > 0 && !showVizPanel) {
      setShowVizPanel(true);
    }
  }, [vizEvents.length, showVizPanel]);

  // ── Streaming Token Accumulation ──────────────────────────────
  // Accumulate stream_token activities into streamingContent

  useEffect(() => {
    if (!isWorking) return;

    const tokenActivities = agentActivity.filter((a) => a.type === "stream_token");
    if (tokenActivities.length === 0) return;

    // Get only new tokens (those added since last check)
    const lastKnownLength = parseInt(streamTokenBufferRef.current, 10) || 0;
    const newTokens = tokenActivities.slice(lastKnownLength);
    if (newTokens.length === 0) return;

    // Update buffer reference
    streamTokenBufferRef.current = String(tokenActivities.length);

    // Accumulate tokens
    const tokenText = newTokens.map((a) => a.content).join("");
    setStreamingContent((prev) => prev + tokenText);
  }, [agentActivity, isWorking]);

  // Reset streaming buffer when agent goes idle
  useEffect(() => {
    if (!isWorking) {
      streamTokenBufferRef.current = "";
    }
  }, [isWorking]);

  // ── Stop Request ──────────────────────────────────────────────

  const handleStop = useCallback(() => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
    }
    setAgentStatus("idle");
    setStreamingContent("");
    clearActivity();
  }, [abortController, setAgentStatus, clearActivity]);

  // ── Send Message ──────────────────────────────────────────────

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isWorking || !activeConversationId) return;

    setInput("");
    clearActivity();
    clearBuildSteps();
    setStreamingContent("");

    addMessage(activeConversationId, { role: "user", content: text });
    setAgentStatus("thinking");

    const controller = new AbortController();
    setAbortController(controller);

    try {
      addActivity({ type: "agent_thinking", content: "Analyse..." });

      const convMessages = [...messages, { role: "user" as const, content: text }];
      let fullContent = "";

      try {
        const res = await nexusApi.chatStream(convMessages, provider, model);
        if (res.body) {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            if (controller.signal.aborted) break;

            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("event: token")) continue;
              if (line.startsWith("data: ")) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.token) {
                    fullContent += data.token;
                    setStreamingContent(fullContent);
                  }
                } catch (error) { /* skip malformed token */ }
              }
            }
          }
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        log.warn('Streaming failed, falling back to non-streaming', error);
        try {
          const res = await nexusApi.chat(convMessages, provider, model);
          fullContent = res.content;
        } catch (fallbackError) {
          log.error('Fallback chat also failed', fallbackError);
          throw fallbackError;
        }
      }

      setStreamingContent("");
      addActivity({ type: "task_done", content: "Reponse generee" });
      addMessage(activeConversationId, { role: "assistant", content: fullContent || "Aucune reponse." });
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : "Impossible de contacter le backend";
      addActivity({ type: "error", content: msg });
      addMessage(activeConversationId, {
        role: "assistant",
        content: `**Erreur :** ${msg}\n\nVerifiez que le backend est lance.`,
      });
    } finally {
      setAgentStatus("idle");
      setAbortController(null);
    }
  }, [input, isWorking, activeConversationId, messages, provider, model, abortController, clearActivity, clearBuildSteps, addMessage, addActivity, setAgentStatus]);

  // ── Run as Agent Task ─────────────────────────────────────────

  const handleRunTask = useCallback(async () => {
    const text = input.trim();
    if (!text || isWorking || !activeConversationId) return;

    setInput("");
    clearActivity();
    clearBuildSteps();

    addMessage(activeConversationId, { role: "user", content: text });
    setAgentStatus("working");

    try {
      addActivity({ type: "agent_thinking", content: "Analyse de la tache..." });
      addActivity({ type: "task_step", content: "Elaboration du plan..." });

      const data = await nexusApi.runTask(text, provider);

      if (data.plan) {
        addActivity({ type: "task_step", content: `Plan : ${data.plan.slice(0, 200)}...` });
      }

      addActivity({ type: "task_step", content: "Execution..." });
      addActivity({ type: "task_done", content: "Tache terminee" });

      addMessage(activeConversationId, {
        role: "assistant",
        content: `## Resultat\n\n**Statut :** ${data.status}\n\n${data.plan ? `**Plan :**\n\n${data.plan}\n\n` : ""}**Resultat :**\n\n${data.result}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Echec";
      addActivity({ type: "error", content: msg });
      addMessage(activeConversationId, { role: "assistant", content: `**Erreur :** ${msg}` });
    } finally {
      setAgentStatus("idle");
    }
  }, [input, isWorking, activeConversationId, provider, addActivity, addMessage, clearActivity, clearBuildSteps, setAgentStatus]);

  // ── Voice Transcription Handler ───────────────────────────────

  const handleVoiceTranscription = useCallback((text: string) => {
    setInput((prev) => {
      const separator = prev.trim() ? " " : "";
      return prev + separator + text;
    });
  }, []);

  // ── Keyboard Handler ──────────────────────────────────────────

  function handleKeyDown(e: React.KeyboardEvent) {
    // Enter to send (without shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Escape to clear input
    if (e.key === "Escape") {
      setInput("");
    }
    // Cmd/Ctrl + / to toggle settings
    if ((e.metaKey || e.ctrlKey) && e.key === "/") {
      e.preventDefault();
      setSettingsOpen(!settingsOpen);
    }
  }

  // ── Layout Decision ──────────────────────────────────────────

  const hasSidePanel = showVizPanel && vizEvents.length > 0;
  const hasArtifactPanel = !!activeArtifact;

  return (
    <div className="flex h-full">
      {/* Conversation Sidebar */}
      <ConversationSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Avatar Zone (left) — only if enabled */}
      {avatarEnabled && !isMobile && (
        <div className="avatar-zone-mobile w-64 xl:w-80 h-full shrink-0 border-r border-border/10 relative overflow-hidden flex items-center justify-center">
          <div className="w-full h-full flex items-center justify-center">
            <VRMAvatar
              expression={avatarExpression}
              thinking={isWorking}
              speaking={streamingContent.length > 0}
              modelUrl={avatarModelUrl ?? undefined}
              professionalMode={avatarProfessionalMode}
            />
          </div>
          {/* Avatar status overlay */}
          <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center gap-1">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-background/80 backdrop-blur-sm border border-border/20" role="status" aria-live="polite">
              <div className={`w-2 h-2 rounded-full ${isWorking ? "bg-cyan-500 animate-pulse" : backendConnected ? "bg-emerald-500" : "bg-red-400"}`} aria-hidden="true" />
              <span className="text-[10px] text-foreground/60">
                {isWorking ? "En reflexion..." : backendConnected ? "Pret" : "Deconnecte"}
              </span>
            </div>
            {/* VRM Hub button */}
            <button
              onClick={() => setVrmHubOpen(true)}
              aria-label="Changer d'avatar"
              className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-background/60 backdrop-blur-sm border border-border/15 hover:border-primary/30 hover:bg-primary/5 transition-colors"
              title="Changer d'avatar"
            >
              <User size={8} className="text-muted-foreground" />
              <span className="text-[8px] text-muted-foreground/70">
                {avatarModelUrl ? "Changer" : "Choisir avatar"}
              </span>
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area — Chat + Side Panels */}
      <div className="chat-container-mobile flex-1 flex min-w-0 h-full">
        <ResizablePanelGroup direction="horizontal">
          {/* Chat Zone */}
          <ResizablePanel defaultSize={hasSidePanel || hasArtifactPanel ? 60 : 100} minSize={40}>
            <div className="flex flex-col h-full">
              {/* Chat Header */}
              <div className="flex items-center gap-2 px-4 py-2 border-b border-border/10 shrink-0">
                <button
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  aria-label={sidebarOpen ? "Fermer l'historique" : "Ouvrir l'historique"}
                  aria-expanded={sidebarOpen}
                  className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
                  title="Historique des conversations"
                >
                  <Menu size={16} />
                </button>
                <span className="text-[12px] text-foreground/60 truncate flex-1">
                  {activeConv?.title || "Nouvelle conversation"}
                </span>
                <button
                  onClick={() => setSettingsOpen(!settingsOpen)}
                  aria-label="Ouvrir les parametres"
                  className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
                  title="Parametres (provider, modele, cle API)"
                >
                  <Settings size={14} />
                </button>
              </div>

              {/* Messages */}
              <div ref={scrollRef} className="flex-1 overflow-y-auto">
                <div className="px-4 py-4 md:px-6 md:py-6 space-y-4 max-w-3xl mx-auto">
                  {messages.map((msg, i) => (
                    <ChatBubble
                      key={msg.id}
                      message={msg}
                      isLast={i === messages.length - 1}
                      avatarExpression={i === messages.length - 1 ? avatarExpression : "neutral"}
                      avatarThinking={i === messages.length - 1 && isWorking}
                      ttsEnabled={ttsEnabled}
                    />
                  ))}

                  {/* Thinking Panel — shows agent reasoning in real-time */}
                  {isWorking && (
                    <ThinkingPanel activities={agentActivity} />
                  )}

                  {/* Streaming content */}
                  <StreamingContent content={streamingContent} />

                  {/* Generative UI: Build steps in chat */}
                  {buildSteps.length > 0 && <BuildStepsCard steps={buildSteps} />}

                  {/* Generative UI: Agent activity in chat */}
                  {isWorking && agentActivity.filter((a) => a.type !== "stream_token").length > 0 && (
                    <AgentActivityCard activities={agentActivity.filter((a) => a.type !== "stream_token").slice(-8)} />
                  )}

                  {/* A2UI Generative Cards (forms, charts, tables) */}
                  {a2uiCards.map((card) => (
                    <A2UIRenderer key={card.card_id} card={card} onAction={(action) => {
                      log.info("A2UI action", { card: card.card_id, action: action.id });
                    }} />
                  ))}

                  {/* HITL Approval Requests */}
                  <ApprovalCard
                    approvals={pendingApprovals}
                    onRemove={removeApprovalRequest}
                  />
                </div>
              </div>

              {/* Input Area */}
              <div className="px-4 py-3 md:px-6 border-t border-border/15 shrink-0">
                <div className="flex gap-2 max-w-3xl mx-auto items-end">
                  {/* Voice Button */}
                  <VoiceButton onTranscription={handleVoiceTranscription} />

                  <div className="flex-1 relative">
                    <Textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Parlez a NEXUS... (Enter = envoyer)"
                      data-chat-input
                      className="min-h-[44px] max-h-[140px] resize-none text-sm bg-muted/15 border-border/25 focus-visible:border-primary/50 focus-visible:ring-primary/20 pr-24"
                      rows={1}
                      disabled={isWorking}
                    />
                    <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
                      {/* TTS Toggle */}
                      <button
                        onClick={() => setTtsEnabled(!ttsEnabled)}
                        aria-label={ttsEnabled ? "Desactiver TTS" : "Activer TTS"}
                        aria-pressed={ttsEnabled}
                        className={`h-7 w-7 flex items-center justify-center rounded-md transition-colors ${
                          ttsEnabled
                            ? "text-emerald-500 hover:bg-emerald-500/10"
                            : "text-muted-foreground hover:bg-muted/30"
                        }`}
                        title={ttsEnabled ? "Desactiver TTS" : "Activer TTS"}
                      >
                        {ttsEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
                      </button>

                      {/* Agent task button */}
                      <Button
                        onClick={handleRunTask}
                        disabled={isWorking || !input.trim()}
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-[11px] gap-1 text-amber-500 hover:text-amber-400"
                        aria-label="Executer comme tache agent"
                        title="Executer comme tache agent"
                      >
                        <Sparkles size={12} />
                        <span className="hidden sm:inline">Agent</span>
                      </Button>

                      {/* Stop button when working */}
                      {isWorking ? (
                        <Button
                          onClick={handleStop}
                          size="sm"
                          variant="destructive"
                          className="h-7 w-7 p-0 rounded-lg"
                          aria-label="Arreter la generation"
                          title="Arreter"
                        >
                          <Square size={12} />
                        </Button>
                      ) : (
                        <Button
                          onClick={handleSend}
                          disabled={!input.trim()}
                          size="sm"
                          className="h-7 w-7 p-0 rounded-lg"
                          aria-label="Envoyer le message"
                          title="Envoyer"
                        >
                          <Send size={13} />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Status bar */}
                <div className="flex items-center justify-between max-w-3xl mx-auto mt-1.5 px-1">
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <button
                      onClick={() => setAgentMode(agentMode === "plan" ? "build" : "plan")}
                      aria-label={`Basculer en mode ${agentMode === "build" ? "Plan" : "Build"}`}
                      aria-pressed={agentMode === "build"}
                      className={`flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors ${
                        agentMode === "build" ? "text-amber-500 hover:bg-amber-500/10" : "text-blue-500 hover:bg-blue-500/10"
                      }`}
                    >
                      {agentMode === "build" ? <Zap size={9} /> : <Shield size={9} />}
                      {agentMode === "build" ? "Build" : "Plan"}
                    </button>
                    <span className="text-muted-foreground/30">|</span>
                    <span className="font-mono">{provider}/{model}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Viz panel toggle */}
                    {vizEvents.length > 0 && (
                      <button
                        onClick={() => setShowVizPanel(!showVizPanel)}
                        aria-label={showVizPanel ? "Masquer la visualisation" : "Afficher la visualisation"}
                        aria-pressed={showVizPanel}
                        className={`flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors text-[10px] ${
                          showVizPanel
                            ? "text-cyan-500 bg-cyan-500/10"
                            : "text-muted-foreground hover:bg-muted/30"
                        }`}
                      >
                        <Eye size={9} />
                        Viz ({vizEvents.length})
                      </button>
                    )}
                    <span className="hidden md:inline text-[9px] text-muted-foreground/40">⌘K commandes · ⌘, parametres</span>
                  </div>
                </div>
              </div>
            </div>
          </ResizablePanel>

          {/* Viz Panel (desktop: side panel, mobile: overlay) */}
          {hasSidePanel && !isMobile && (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel defaultSize={25} minSize={15} maxSize={40}>
                <LiveVizPanel
                  events={vizEvents}
                  onClose={() => {
                    setShowVizPanel(false);
                    clearVizEvents();
                  }}
                />
              </ResizablePanel>
            </>
          )}

          {/* Artifact Panel (desktop: side panel, mobile: overlay) */}
          {hasArtifactPanel && activeArtifact && !hasSidePanel && !isMobile && (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel defaultSize={30} minSize={15} maxSize={50}>
                <ArtifactPanel
                  artifact={activeArtifact}
                  onClose={() => setActiveArtifact(null)}
                />
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </div>

      {/* Mobile viz panel overlay */}
      {hasSidePanel && isMobile && (
        <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col">
          <LiveVizPanel
            events={vizEvents}
            onClose={() => {
              setShowVizPanel(false);
              clearVizEvents();
            }}
          />
        </div>
      )}

      {/* Mobile artifact overlay */}
      {hasArtifactPanel && activeArtifact && isMobile && (
        <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col">
          <ArtifactPanel
            artifact={activeArtifact}
            onClose={() => setActiveArtifact(null)}
          />
        </div>
      )}

      {/* VRM Hub Modal */}
      <VRMHubModal
        open={vrmHubOpen}
        onClose={() => setVrmHubOpen(false)}
        onSelect={(url) => setAvatarModelUrl(url)}
        currentModelUrl={avatarModelUrl ?? undefined}
      />
    </div>
  );
}
