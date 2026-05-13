"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { useNexusStore } from "@/lib/nexus-store";
import { api, type ChatMessage } from "@/lib/nexus-api";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Send, Bot, Loader2, Sparkles, Terminal, PanelRight, PanelRightOpen,
  Shield, Zap, File, Pencil, GitBranch,
} from "lucide-react";

/* ── SVG Avatar Canvas (CSS art) ── */
function AvatarCanvas({ expression, thinking }: { expression: string; thinking: boolean }) {
  const mouthMap: Record<string, string> = {
    neutral: "M38 62 Q50 66 62 62",
    joy: "M36 60 Q50 72 64 60",
    thinking: "M38 62 Q50 64 62 62",
    surprise: "M38 63 Q50 70 62 63",
    relaxed: "M38 63 Q50 65 62 63",
    sad: "M38 64 Q50 60 62 64",
    angry: "M38 61 L42 65 L50 61 L58 65 L62 61",
  };
  const mouthD = mouthMap[expression] || mouthMap.neutral;
  const eyeY = expression === "joy" ? 40 : 42;

  return (
    <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-lg">
      <defs>
        <radialGradient id="av-grad" cx="50%" cy="35%" r="55%">
          <stop offset="0%" stopColor="#5eead4" />
          <stop offset="50%" stopColor="#06b6d4" />
          <stop offset="100%" stopColor="#0e7490" />
        </radialGradient>
        <radialGradient id="av-glow" cx="50%" cy="50%" r="50%">
          <stop offset="60%" stopColor="rgba(6,182,212,0.15)" />
          <stop offset="100%" stopColor="rgba(6,182,212,0)" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="52" fill="url(#av-glow)" />
      <circle cx="50" cy="50" r="45" fill="url(#av-grad)" opacity={thinking ? 0.7 : 0.9} />
      <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      {thinking && (
        <>
          <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(94,234,212,0.3)" strokeWidth="1.5" strokeDasharray="6 4">
            <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="4s" repeatCount="indefinite" />
          </circle>
          <circle cx="50" cy="50" r="51" fill="none" stroke="rgba(6,182,212,0.15)" strokeWidth="1" strokeDasharray="3 6">
            <animateTransform attributeName="transform" type="rotate" from="360 50 50" to="0 50 50" dur="3s" repeatCount="indefinite" />
          </circle>
        </>
      )}
      <g fill="white">
        <ellipse cx="33" cy={eyeY} rx="5.5" ry="6" />
        <ellipse cx="67" cy={eyeY} rx="5.5" ry="6" />
        <ellipse cx="34.5" cy={eyeY + 0.5} rx="2.5" ry="3" fill="#0f172a" />
        <ellipse cx="68.5" cy={eyeY + 0.5} rx="2.5" ry="3" fill="#0f172a" />
        <circle cx="36" cy={eyeY - 1} r="1" fill="rgba(255,255,255,0.6)" />
        <circle cx="70" cy={eyeY - 1} r="1" fill="rgba(255,255,255,0.6)" />
      </g>
      {expression === "joy" ? (
        <path d={mouthD} stroke="white" strokeWidth="2.8" fill="none" strokeLinecap="round" />
      ) : (
        <path d={mouthD} stroke="white" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      )}
    </svg>
  );
}

/* ── Avatar Sidebar (right panel) ── */
function AvatarSidebar({ expression, thinking }: { expression: string; thinking: boolean }) {
  const expressionLabels: Record<string, string> = {
    neutral: "\u{1F610} Neutre",
    joy: "\u{1F600} Joyeux",
    thinking: "\u{1F914} R\u00E9fl\u00E9chit...",
    surprise: "\u{1F62E} Surpris",
    relaxed: "\u{1F60C} D\u00E9tendu",
    sad: "\u{1F622} Triste",
    angry: "\u{1F620} F\u00E2ch\u00E9",
  };

  return (
    <div className="w-72 border-l border-border/60 flex flex-col shrink-0 bg-gradient-to-b from-transparent via-background to-background">
      <div className="px-3 py-2 border-b border-border/40 flex items-center justify-between shrink-0">
        <h2 className="text-xs font-semibold tracking-wide text-foreground/80">
          🎭 Avatar VRM
        </h2>
        <span className={`inline-block w-2 h-2 rounded-full ${thinking ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]" : "bg-muted-foreground/40"}`} />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-6 gap-3">
        <div className="w-44 h-44">
          <AvatarCanvas expression={expression} thinking={thinking} />
        </div>

        <p className="text-xs font-medium text-foreground/70">
          {expressionLabels[expression] || expressionLabels.neutral}
        </p>

        <div className="flex items-center gap-1.5 mt-1">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${thinking ? "bg-green-500" : "bg-muted-foreground/30"}`} />
          <span className="text-[10px] text-muted-foreground/60 tracking-wide uppercase">
            {thinking ? "En r\u00E9flexion" : "En veille"}
          </span>
        </div>

        <div className="mt-2 px-3 py-1.5 rounded-md bg-primary/5 border border-primary/10">
          <span className="text-[10px] text-primary/60 flex items-center gap-1.5">
            <Bot size={10} />
            Avatar VRM actif
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Activity Feed ── */
function ActivityFeed() {
  const { agentActivity } = useNexusStore();
  const recent = agentActivity.slice(-5);

  if (recent.length === 0) {
    return <span className="text-xs text-muted-foreground">NEXUS réfléchit...</span>;
  }

  return (
    <div className="space-y-1 flex-1 min-w-0">
      {recent.map((a, i) => (
        <motion.div
          key={a.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: "easeOut", delay: i * 0.04 }}
          className="flex items-center gap-2 text-xs"
        >
          {a.type === "thought" && <Loader2 size={10} className="animate-spin shrink-0 text-cyan-400" />}
          {a.type === "tool_call" && <Terminal size={10} className="text-blue-400 shrink-0" />}
          {a.type === "tool_result" && <span className="text-green-400 shrink-0">✓</span>}
          {a.type === "task_step" && <span className="text-yellow-400 shrink-0">→</span>}
          {a.type === "task_done" && <span className="text-green-400 shrink-0">✓</span>}
          {a.type === "error" && <span className="text-red-400 shrink-0">✗</span>}
          {a.type === "file_create" && <File size={10} className="text-emerald-400 shrink-0" />}
          {a.type === "file_edit" && <Pencil size={10} className="text-amber-400 shrink-0" />}
          {a.type === "code_diff" && <GitBranch size={10} className="text-purple-400 shrink-0" />}
          <span className="truncate text-muted-foreground">
            {a.content.replace(/\*\*/g, "").slice(0, 120)}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

/* ── Chat Bubble ── */
function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] rounded-xl px-4 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {isUser ? (
          message.content
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
                        customStyle={{ fontSize: "0.8rem", borderRadius: "0.375rem" }}
                      >
                        {code}
                      </SyntaxHighlighter>
                    );
                  }
                  return (
                    <code className="bg-muted-foreground/20 px-1 py-0.5 rounded text-xs" {...props}>
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

/* ── Main Chat Panel ── */
export function ChatPanel() {
  const {
    conversations, activeConversationId, addConversation,
    addMessage, setActiveConversation, provider, model,
    agentThinking, setAgentThinking, addActivity, clearActivity,
    avatarEnabled, toggleAvatar, agentMode, setAgentMode,
  } = useNexusStore();

  const [input, setInput] = useState("");
  const [avatarExpression, setAvatarExpression] = useState("neutral");
  const [showFullActivity, setShowFullActivity] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConv?.messages ?? [];

  useEffect(() => {
    if (!activeConversationId) {
      const id = addConversation();
      addMessage(id, {
        role: "assistant",
        content: "Bonjour ! Je suis **NEXUS**, votre agent IA souverain.\n\nParlez-moi librement \u2014 je peux chercher sur le web, ex\u00E9cuter du code, g\u00E9rer la m\u00E9moire, et bien plus.",
      });
    }
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    }
  }, [messages, agentThinking]);

  useEffect(() => {
    if (agentThinking) {
      setAvatarExpression("thinking");
      setShowFullActivity(true);
    } else {
      setAvatarExpression("joy");
      const exprTimer = setTimeout(() => setAvatarExpression("neutral"), 3000);
      const activityTimer = setTimeout(() => setShowFullActivity(false), 4000);
      return () => { clearTimeout(exprTimer); clearTimeout(activityTimer); };
    }
  }, [agentThinking]);

  async function handleSend() {
    const text = input.trim();
    if (!text || agentThinking || !activeConversationId) return;
    setInput("");
    clearActivity();

    addMessage(activeConversationId, { role: "user", content: text });
    setAgentThinking(true);

    try {
      addActivity({ type: "thought", content: "Analyse de votre demande..." });
      const convMessages = [...messages, { role: "user" as const, content: text }];
      const res = await api.chat(convMessages, provider, model);
      addActivity({ type: "task_done", content: "R\u00E9ponse g\u00E9n\u00E9r\u00E9e" });
      addMessage(activeConversationId, { role: "assistant", content: res.content });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de contacter le backend";
      addActivity({ type: "error", content: msg });
      addMessage(activeConversationId, {
        role: "assistant",
        content: `**Erreur :** ${msg}\n\nV\u00E9rifiez que le backend est lanc\u00E9.`,
      });
    } finally {
      setAgentThinking(false);
    }
  }

  async function handleRunTask(task?: string) {
    const t = task || input.trim();
    if (!t || agentThinking || !activeConversationId) return;
    setInput("");
    clearActivity();

    addMessage(activeConversationId, { role: "user", content: `\u{1F9E0} T\u00E2che : ${t}` });
    setAgentThinking(true);
    addActivity({ type: "thought", content: "Analyse de la t\u00E2che..." });

    try {
      addActivity({ type: "task_step", content: "\u00C9laboration du plan..." });
      const data = await api.runTask(t);
      if (data.plan) {
        addActivity({ type: "task_step", content: `**Plan \u00E9tabli** : ${data.plan.slice(0, 300)}...` });
      }
      addActivity({ type: "task_step", content: "Ex\u00E9cution en cours..." });
      addActivity({ type: "task_done", content: `**R\u00E9sultat** : ${data.result}` });
      addMessage(activeConversationId, {
        role: "assistant",
        content: `## R\u00E9sultat de la t\u00E2che\n\n**Statut :** ${data.status}\n\n${data.plan ? `**Plan :**\n\n${data.plan}\n\n` : ""}**R\u00E9sultat :**\n\n${data.result}`,
      });
    } catch (err: unknown) {
      addActivity({ type: "error", content: err instanceof Error ? err.message : "\u00C9chec" });
      addMessage(activeConversationId, {
        role: "assistant", content: `**Erreur d'ex\u00E9cution** : ${err instanceof Error ? err.message : "\u00C9chec inconnu"}`,
      });
    } finally {
      setAgentThinking(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const activityCount = useNexusStore((s) => s.agentActivity.length);

  return (
    <div className="flex h-full">
      {/* Chat Principal */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border/60 shrink-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold tracking-tight">NEXUS</h1>
            <Badge variant="outline" className="text-[10px] font-mono">{provider}</Badge>
            <Badge variant="secondary" className="text-[10px] font-mono">{model}</Badge>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => setAgentMode(agentMode === "plan" ? "build" : "plan")}
              title={`Mode\u00A0: ${agentMode === "plan" ? "Plan" : "Build"}`}
            >
              {agentMode === "plan" ? <Shield size={14} className="text-blue-400" /> : <Zap size={14} className="text-amber-400" />}
            </Button>
            <Button variant="ghost" size="icon" className="size-7" onClick={toggleAvatar} title="Avatar VRM">
              {avatarEnabled ? <PanelRightOpen size={15} /> : <PanelRight size={15} />}
            </Button>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea ref={scrollRef} className="flex-1">
          <div className="px-4 py-3 space-y-4 max-w-4xl mx-auto">
            {messages.map((msg, i) => (
              <ChatBubble key={i} message={msg} />
            ))}

            {/* Thinking indicator + activity */}
            {agentThinking && showFullActivity && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/40 border border-border/30">
                <Loader2 size={16} className="animate-spin text-primary shrink-0 mt-0.5" />
                <ActivityFeed />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="px-4 py-3 border-t border-border/60 shrink-0 bg-gradient-to-t from-background via-background to-transparent">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Écrivez votre message... (Enter = envoyer, Shift+Enter = saut de ligne)"
              className="min-h-[44px] max-h-[160px] resize-none text-sm bg-muted/30 border-border/50 focus-visible:border-cyan-500/50 focus-visible:ring-cyan-500/20"
              rows={1}
              disabled={agentThinking}
            />
            <div className="flex flex-col gap-1">
              <Button onClick={handleSend} disabled={agentThinking || !input.trim()} className="h-[44px] aspect-square" title="Envoyer">
                {agentThinking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </Button>
              <Button onClick={() => handleRunTask()} disabled={agentThinking || !input.trim()} variant="secondary" className="h-[44px] aspect-square"               title="Exécuter comme tâche">
                <Sparkles size={16} />
              </Button>
            </div>
          </div>
          {/* Collapsed activity summary after thinking */}
          {!agentThinking && activityCount > 0 && !showFullActivity && (
            <div className="max-w-4xl mx-auto mt-1.5">
              <p className="text-[10px] text-muted-foreground/40">
                ✓ {activityCount} action{activityCount > 1 ? "s" : ""} exécutée{activityCount > 1 ? "s" : ""}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* VRM Avatar Sidebar */}
      <AnimatePresence>
        {avatarEnabled && (
          <motion.div
            key="avatar-sidebar"
            initial={{ opacity: 0, x: 60 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 60 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            <AvatarSidebar expression={avatarExpression} thinking={agentThinking} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
