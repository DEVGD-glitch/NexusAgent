// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Chat Panel (Agent-First with Avatar + Brick-by-Brick)
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { NexusAvatar } from "./avatar";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Send, Loader2, Sparkles, Shield, Zap, Bot,
  File, Pencil, Terminal, Check, X, AlertCircle,
  Code2, GitBranch, Package, Wrench,
} from "lucide-react";
import type { ChatMessage, AgentActivity, BuildStep } from "@/types/nexus";

// ── Chat Bubble ─────────────────────────────────────────────

function ChatBubble({ message, avatarExpression, avatarThinking }: { message: ChatMessage; avatarExpression: string; avatarThinking: boolean }) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar on assistant messages */}
      {!isUser && (
        <div className="shrink-0 mt-1">
          <NexusAvatar expression={avatarExpression as any} thinking={avatarThinking} size={32} inline />
        </div>
      )}

      <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? "bg-primary text-primary-foreground rounded-tr-sm"
          : "bg-muted/80 text-foreground rounded-tl-sm border border-border/30"
      }`}>
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const code = String(children).replace(/\n$/, "");
                  if (match) {
                    return (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ fontSize: "0.78rem", borderRadius: "0.5rem", margin: "0.5rem 0" }}
                      >
                        {code}
                      </SyntaxHighlighter>
                    );
                  }
                  return (
                    <code className="bg-muted-foreground/15 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── Activity Feed (Real-time Agent Visualization) ───────────

function ActivityItem({ activity }: { activity: AgentActivity }) {
  const iconMap: Record<string, React.ReactNode> = {
    agent_thinking: <Loader2 size={12} className="animate-spin text-cyan-400" />,
    agent_action: <Bot size={12} className="text-teal-400" />,
    tool_call: <Terminal size={12} className="text-blue-400" />,
    tool_result: <Check size={12} className="text-emerald-400" />,
    file_create: <File size={12} className="text-emerald-400" />,
    file_edit: <Pencil size={12} className="text-amber-400" />,
    code_building: <Code2 size={12} className="text-purple-400" />,
    task_step: <GitBranch size={12} className="text-yellow-400" />,
    task_done: <Check size={12} className="text-emerald-500" />,
    error: <AlertCircle size={12} className="text-red-400" />,
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15 }}
      className="flex items-start gap-2 py-1"
    >
      <span className="shrink-0 mt-0.5">{iconMap[activity.type] || <Wrench size={12} className="text-muted-foreground" />}</span>
      <span className="text-xs text-muted-foreground leading-relaxed break-all">
        {activity.content.slice(0, 200)}
      </span>
    </motion.div>
  );
}

// ── Build Visualization (Brick-by-Brick) ────────────────────

function BuildVisualization({ steps }: { steps: BuildStep[] }) {
  if (steps.length === 0) return null;

  const iconMap: Record<string, React.ReactNode> = {
    file_create: <File size={14} />,
    file_edit: <Pencil size={14} />,
    code_line: <Code2 size={14} />,
    dependency: <Package size={14} />,
    config: <Wrench size={14} />,
    test: <Check size={14} />,
    deploy: <GitBranch size={14} />,
  };

  return (
    <div className="rounded-xl border border-border/40 bg-card/50 p-4 space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-foreground/80">
        <Code2 size={14} className="text-primary" />
        <span>Construction en cours</span>
        <span className="text-muted-foreground">({steps.filter(s => s.status === "completed").length}/{steps.length})</span>
      </div>

      <div className="space-y-1.5 max-h-60 overflow-y-auto">
        {steps.map((step, i) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15, delay: i * 0.03 }}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-muted/30"
          >
            <span className={`shrink-0 ${
              step.status === "completed" ? "text-emerald-500" :
              step.status === "building" ? "text-amber-500 animate-pulse" :
              step.status === "error" ? "text-red-500" : "text-muted-foreground"
            }`}>
              {iconMap[step.type] || <Wrench size={14} />}
            </span>
            <span className="text-xs text-foreground/80 truncate flex-1">{step.label}</span>
            {step.status === "building" && step.progress > 0 && (
              <Progress value={step.progress} className="w-16 h-1" />
            )}
            {step.status === "completed" && <Check size={12} className="text-emerald-500 shrink-0" />}
            {step.status === "error" && <X size={12} className="text-red-500 shrink-0" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ── Main Chat Panel ─────────────────────────────────────────

export function ChatPanel() {
  const {
    conversations, activeConversationId, addConversation,
    addMessage, provider, model,
    agentStatus, setAgentStatus, addActivity, clearActivity,
    avatarExpression, avatarEnabled, agentMode, setAgentMode,
    agentActivity, buildSteps, clearBuildSteps,
  } = useNexusStore();

  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConv?.messages ?? [];
  const isWorking = agentStatus !== "idle";

  // Initialize first conversation
  useEffect(() => {
    if (!activeConversationId) {
      const id = addConversation();
      addMessage(id, {
        role: "assistant",
        content: "Bonjour ! Je suis **NEXUS**, votre agent IA souverain.\n\nJe peux chercher sur le web, executer du code, gerer la memoire, construire des projets, et bien plus.\n\nComment puis-je vous aider ?",
      });
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    }
  }, [messages, agentActivity, streamingContent, buildSteps]);

  // Send message
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isWorking || !activeConversationId) return;

    setInput("");
    clearActivity();
    clearBuildSteps();
    setStreamingContent("");

    addMessage(activeConversationId, { role: "user", content: text });
    setAgentStatus("thinking");

    try {
      addActivity({ type: "agent_thinking", content: "Analyse de votre demande..." });

      // Try streaming first
      const convMessages = [...messages, { role: "user" as const, content: text }];
      let fullContent = "";

      try {
        const res = await nexusApi.chatStream(convMessages, provider, model);
        if (res.body) {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
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
                } catch { /* skip malformed */ }
              }
            }
          }
        }
      } catch {
        // Fallback to non-streaming
        const res = await nexusApi.chat(convMessages, provider, model);
        fullContent = res.content;
      }

      setStreamingContent("");
      addActivity({ type: "task_done", content: "Reponse generee" });
      addMessage(activeConversationId, { role: "assistant", content: fullContent || "Aucune reponse." });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de contacter le backend";
      addActivity({ type: "error", content: msg });
      addMessage(activeConversationId, {
        role: "assistant",
        content: `**Erreur :** ${msg}\n\nVerifiez que le backend est lance.`,
      });
    } finally {
      setAgentStatus("idle");
    }
  }, [input, isWorking, activeConversationId, messages, provider, model]);

  // Run as agent task
  const handleRunTask = useCallback(async () => {
    const text = input.trim();
    if (!text || isWorking || !activeConversationId) return;

    setInput("");
    clearActivity();
    clearBuildSteps();

    addMessage(activeConversationId, { role: "user", content: `Tache : ${text}` });
    setAgentStatus("working");

    try {
      addActivity({ type: "agent_thinking", content: "Analyse de la tache..." });
      addActivity({ type: "task_step", content: "Elaboration du plan..." });

      const data = await nexusApi.runTask(text, provider);

      if (data.plan) {
        addActivity({ type: "task_step", content: `Plan etabli : ${data.plan.slice(0, 200)}...` });
      }

      addActivity({ type: "task_step", content: "Execution en cours..." });
      addActivity({ type: "task_done", content: "Tache terminee" });

      addMessage(activeConversationId, {
        role: "assistant",
        content: `## Resultat de la tache\n\n**Statut :** ${data.status}\n\n${data.plan ? `**Plan :**\n\n${data.plan}\n\n` : ""}**Resultat :**\n\n${data.result}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Echec";
      addActivity({ type: "error", content: msg });
      addMessage(activeConversationId, {
        role: "assistant",
        content: `**Erreur d'execution** : ${msg}`,
      });
    } finally {
      setAgentStatus("idle");
    }
  }, [input, isWorking, activeConversationId, provider]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-14 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-2">
          {avatarEnabled && (
            <NexusAvatar expression={avatarExpression} thinking={isWorking} size={28} />
          )}
          <h1 className="text-sm font-semibold">NEXUS Chat</h1>
          <Badge variant="outline" className="text-[10px] font-mono">{provider}</Badge>
          <Badge variant="secondary" className="text-[10px] font-mono">{model}</Badge>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAgentMode(agentMode === "plan" ? "build" : "plan")}
            className={`gap-1.5 text-xs h-8 ${agentMode === "build" ? "text-amber-500 bg-amber-500/10" : "text-blue-500 bg-blue-500/10"}`}
          >
            {agentMode === "plan" ? <Shield size={13} /> : <Zap size={13} />}
            {agentMode === "plan" ? "Plan" : "Build"}
          </Button>
        </div>
      </div>

      {/* Messages + Activity */}
      <ScrollArea ref={scrollRef} className="flex-1">
        <div className="px-4 py-4 space-y-4 max-w-4xl mx-auto">
          {messages.map((msg, i) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              avatarExpression={i === messages.length - 1 ? avatarExpression : "neutral"}
              avatarThinking={i === messages.length - 1 && isWorking}
            />
          ))}

          {/* Streaming content */}
          {streamingContent && (
            <div className="flex gap-3">
              <div className="shrink-0 mt-1">
                <NexusAvatar expression="thinking" thinking={true} size={32} inline />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed bg-muted/80 border border-border/30">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {streamingContent}
                  </ReactMarkdown>
                </div>
                <span className="inline-block w-1.5 h-4 bg-primary/70 animate-pulse rounded-sm ml-0.5" />
              </div>
            </div>
          )}

          {/* Build Visualization (Brick-by-Brick) */}
          {buildSteps.length > 0 && <BuildVisualization steps={buildSteps} />}

          {/* Real-time Activity Feed */}
          {isWorking && agentActivity.length > 0 && (
            <div className="rounded-xl border border-border/30 bg-muted/20 p-3 space-y-0.5">
              <div className="flex items-center gap-2 mb-2 text-xs font-medium text-foreground/70">
                <Loader2 size={12} className="animate-spin text-primary" />
                <span>NEXUS travaille...</span>
              </div>
              {agentActivity.slice(-10).map((a) => (
                <ActivityItem key={a.id} activity={a} />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="px-4 py-3 border-t border-border/40 shrink-0 bg-gradient-to-t from-background to-transparent">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ecrivez votre message... (Enter = envoyer)"
            className="min-h-[44px] max-h-[140px] resize-none text-sm bg-muted/20 border-border/40 focus-visible:border-primary/50 focus-visible:ring-primary/20"
            rows={1}
            disabled={isWorking}
          />
          <div className="flex flex-col gap-1 shrink-0">
            <Button
              onClick={handleSend}
              disabled={isWorking || !input.trim()}
              className="h-[44px] w-[44px] rounded-xl"
              title="Envoyer"
            >
              {isWorking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </Button>
            <Button
              onClick={handleRunTask}
              disabled={isWorking || !input.trim()}
              variant="secondary"
              className="h-[44px] w-[44px] rounded-xl"
              title="Executer comme tache agent"
            >
              <Sparkles size={16} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
