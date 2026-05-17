// ═══════════════════════════════════════════════════════════════
// NEXUS — Chat Bubble Component
// Renders individual messages (user/assistant) with generative UI
// ═══════════════════════════════════════════════════════════════

"use client";

import React from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Zap } from "lucide-react";
import {
  AgentActivityCard, MemoryCard, WebResultCard,
  CodeResultCard, KnowledgeCard,
} from "./gen-ui";
import { TTSPlayback } from "./voice-ui";
import type { ChatMessage, AgentActivity } from "@/types/nexus";

// ── Activity Type → Card Renderer ───────────────────────────
// Maps activity types to the appropriate GenUI card

function ActivityCards({ activities }: { activities: AgentActivity[] }) {
  const memoryActivities = activities.filter((a) =>
    a.type.includes("memory") || (a.toolName && a.toolName.includes("memory"))
  );
  const webActivities = activities.filter((a) =>
    a.type.includes("web") || (a.toolName && a.toolName.includes("web_search"))
  );
  const codeActivities = activities.filter((a) =>
    a.type.includes("code") || a.type.includes("execute") ||
    (a.toolName && (a.toolName.includes("code") || a.toolName.includes("execute")))
  );
  const knowledgeActivities = activities.filter((a) =>
    a.type.includes("knowledge") || (a.toolName && a.toolName.includes("knowledge"))
  );

  return (
    <>
      {memoryActivities.length > 0 && (
        <MemoryCard
          results={memoryActivities.map((a) => ({
            text: a.content,
            source: a.toolName || "memory",
            distance: 0,
          }))}
        />
      )}
      {webActivities.length > 0 && (
        <WebResultCard
          results={webActivities.map((a) => {
            try {
              const parsed = JSON.parse(a.content);
              if (Array.isArray(parsed)) {
                return parsed.map((r: { title?: string; url?: string; snippet?: string }) => ({
                  title: r.title || "",
                  url: r.url || "",
                  snippet: r.snippet || "",
                }));
              }
              if (parsed.results && Array.isArray(parsed.results)) {
                return parsed.results.map((r: { title?: string; url?: string; snippet?: string }) => ({
                  title: r.title || "",
                  url: r.url || "",
                  snippet: r.snippet || "",
                }));
              }
            } catch { /* JSON parse expected for web results */ }
            return [{ title: a.content.slice(0, 80), url: "", snippet: a.content.slice(0, 200) }];
          }).flat()}
        />
      )}
      {codeActivities.length > 0 && (
        <CodeResultCard
          stdout={codeActivities.map((a) => {
            try {
              const parsed = JSON.parse(a.content);
              return parsed.stdout || parsed.output || a.content;
            } catch { return a.content; }
          }).join("\n")}
          stderr={codeActivities.reduce((acc, a) => {
            try {
              const parsed = JSON.parse(a.content);
              return acc + (parsed.stderr || "");
            } catch { return acc; }
          }, "")}
          exitCode={codeActivities.reduce((code, a) => {
            try {
              const parsed = JSON.parse(a.content);
              return parsed.exit_code ?? parsed.exitCode ?? code;
            } catch { return code; }
          }, 0)}
          timeMs={codeActivities.reduce((ms, a) => {
            try {
              const parsed = JSON.parse(a.content);
              return ms + (parsed.execution_time_ms ?? parsed.timeMs ?? 0);
            } catch { return ms; }
          }, 0)}
        />
      )}
      {knowledgeActivities.length > 0 && (
        <KnowledgeCard
          entities={knowledgeActivities.map((a) => {
            try {
              const parsed = JSON.parse(a.content);
              if (Array.isArray(parsed)) return parsed;
              return [{ name: a.content.slice(0, 60), type: "entity" }];
            } catch {
              return [{ name: a.content.slice(0, 60), type: "entity" }];
            }
          }).flat()}
        />
      )}
    </>
  );
}

// ── Chat Bubble Props ───────────────────────────────────────

interface ChatBubbleProps {
  message: ChatMessage;
  isLast: boolean;
  avatarExpression: string;
  avatarThinking: boolean;
  ttsEnabled: boolean;
}

// ── Chat Bubble Component ───────────────────────────────────

export const ChatBubble = React.memo(function ChatBubble({
  message,
  isLast,
  avatarExpression,
  avatarThinking,
  ttsEnabled,
}: ChatBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {!isUser && (
        <div className="shrink-0 mt-1 w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center">
          <Zap size={12} className="text-white" />
        </div>
      )}
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? "bg-primary text-primary-foreground rounded-tr-sm"
          : "bg-muted/40 text-foreground rounded-tl-sm border border-border/15"
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

        {/* Generative UI: embedded activity cards for this message */}
        {message.activities && message.activities.length > 0 && (
          <div className="mt-3 space-y-2">
            {(() => {
              const thinkingActivities = message.activities.filter((a) =>
                ["agent_thinking", "agent_action", "task_step", "tool_call", "task_done"].includes(a.type)
              );
              const specialActivities = message.activities.filter((a) =>
                !["agent_thinking", "agent_action", "task_step", "tool_call", "task_done", "stream_token"].includes(a.type)
              );

              return (
                <>
                  {thinkingActivities.length > 0 && (
                    <AgentActivityCard activities={thinkingActivities} />
                  )}
                  {specialActivities.length > 0 && (
                    <ActivityCards activities={specialActivities} />
                  )}
                </>
              );
            })()}
          </div>
        )}

        {/* TTS playback button for assistant messages */}
        {!isUser && ttsEnabled && message.content && (
          <div className="mt-2 flex justify-end">
            <TTSPlayback text={message.content.slice(0, 500)} />
          </div>
        )}
      </div>
    </motion.div>
  );
});
