// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat View (Central Hub, like Cursor/Windsurf)
// Everything happens here: chat, agent activity, build viz
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { NexusAvatar } from "./avatar";
import { ActivityFeed } from "./activity-feed";
import { BuildVisualization } from "./build-viz";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Send, Loader2, Sparkles, PanelRightOpen, Shield, Zap, Bot,
  File, Pencil, Terminal, Check, Code2, Package, Wrench, X,
} from "lucide-react";
import type { ChatMessage, BuildStep } from "@/types/nexus";

// ── Chat Bubble ─────────────────────────────────────────────

function ChatBubble({ message, avatarExpression, avatarThinking }: {
  message: ChatMessage; avatarExpression: string; avatarThinking: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {!isUser && (
        <div className="shrink-0 mt-1">
          <NexusAvatar expression={avatarExpression as any} thinking={avatarThinking} size={32} />
        </div>
      )}
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? "bg-primary text-primary-foreground rounded-tr-sm"
          : "bg-muted/60 text-foreground rounded-tl-sm border border-border/20"
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

// ── Main Chat View ──────────────────────────────────────────

export function ChatView() {
  const {
    conversations, activeConversationId, addConversation,
    addMessage, provider, model,
    agentStatus, setAgentStatus, addActivity, clearActivity,
    avatarExpression, avatarEnabled, agentMode, setAgentMode,
    agentActivity, buildSteps, clearBuildSteps,
    contextOpen, openContext,
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
        content: "Bonjour ! Je suis **NEXUS**, votre agent IA souverain.\n\nJe peux chercher, coder, memoriser, construire — tout depuis cette conversation.\n\nComment puis-je vous aider ?",
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
                } catch { /* skip */ }
              }
            }
          }
        }
      } catch {
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
  }, [input, isWorking, activeConversationId, provider]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="px-6 py-6 space-y-5 max-w-3xl mx-auto">
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
                <NexusAvatar expression="thinking" thinking={true} size={32} />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed bg-muted/60 border border-border/20">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
                </div>
                <span className="inline-block w-1.5 h-4 bg-primary/70 animate-pulse rounded-sm ml-0.5" />
              </div>
            </div>
          )}

          {/* Build Visualization */}
          {buildSteps.length > 0 && <BuildVisualization steps={buildSteps} />}

          {/* Activity Feed (inline, compact) */}
          {isWorking && agentActivity.length > 0 && (
            <ActivityFeed activities={agentActivity.slice(-8)} />
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="px-6 py-3 border-t border-border/20 shrink-0">
        <div className="flex gap-2 max-w-3xl mx-auto items-end">
          <div className="flex-1 relative">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Envoyez un message... (Enter = envoyer, Shift+Enter = saut de ligne)"
              className="min-h-[44px] max-h-[140px] resize-none text-sm bg-muted/20 border-border/30 focus-visible:border-primary/50 focus-visible:ring-primary/20 pr-24"
              rows={1}
              disabled={isWorking}
            />
            {/* Inline action buttons inside textarea */}
            <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
              <Button
                onClick={handleRunTask}
                disabled={isWorking || !input.trim()}
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs gap-1 text-amber-500 hover:text-amber-400"
                title="Executer comme tache agent (Build mode)"
              >
                <Sparkles size={13} />
                <span className="hidden sm:inline">Agent</span>
              </Button>
              <Button
                onClick={handleSend}
                disabled={isWorking || !input.trim()}
                size="sm"
                className="h-7 w-7 p-0 rounded-lg"
                title="Envoyer"
              >
                {isWorking ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </Button>
            </div>
          </div>
        </div>

        {/* Status bar */}
        <div className="flex items-center justify-between max-w-3xl mx-auto mt-1.5 px-1">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <button
              onClick={() => setAgentMode(agentMode === "plan" ? "build" : "plan")}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors ${
                agentMode === "build" ? "text-amber-500 hover:bg-amber-500/10" : "text-blue-500 hover:bg-blue-500/10"
              }`}
            >
              {agentMode === "build" ? <Zap size={10} /> : <Shield size={10} />}
              {agentMode === "build" ? "Build" : "Plan"}
            </button>
            <span className="text-muted-foreground/40">|</span>
            <span className="font-mono">{provider}/{model}</span>
          </div>
          <button
            onClick={() => openContext()}
            className={`text-[11px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 ${contextOpen ? "text-primary" : ""}`}
          >
            <PanelRightOpen size={12} />
            {contextOpen ? "Fermer" : "Details"}
          </button>
        </div>
      </div>
    </div>
  );
}
