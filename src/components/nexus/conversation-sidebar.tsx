// ═══════════════════════════════════════════════════════════════
// NEXUS — Conversation Sidebar
// Collapsible left panel listing past conversations.
// Desktop: persistent. Mobile: overlay with backdrop.
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useMemo, useCallback, memo } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useNexusStore } from "@/lib/nexus-store";
import { useIsMobile } from "@/hooks/use-mobile";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Search,
  Trash2,
  MessageSquare,
  X,
  PanelLeftClose,
} from "lucide-react";
import type { Conversation } from "@/types/nexus";

// ── Helpers ─────────────────────────────────────────────────

function formatDate(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffDays === 0) {
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }
  if (diffDays === 1) return "Hier";
  if (diffDays < 7) {
    return d.toLocaleDateString("fr-FR", { weekday: "long" });
  }
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

function previewText(conv: Conversation): string {
  const firstUser = conv.messages.find((m) => m.role === "user");
  if (firstUser) {
    const text = firstUser.content.replace(/[#*`\n\r]+/g, " ").trim();
    return text.length > 60 ? text.slice(0, 60) + "..." : text;
  }
  return conv.title || "Nouvelle conversation";
}

// ── Conversation Item (memoized) ───────────────────────────

interface ConversationItemProps {
  conv: Conversation;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const ConversationItem = memo(function ConversationItem({
  conv,
  isActive,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (confirmDelete) {
        onDelete(conv.id);
        setConfirmDelete(false);
      } else {
        setConfirmDelete(true);
        // Auto-cancel after 3s
        setTimeout(() => setConfirmDelete(false), 3000);
      }
    },
    [confirmDelete, conv.id, onDelete],
  );

  return (
    <div
      onClick={() => onSelect(conv.id)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(conv.id); }}}
      role="button"
      tabIndex={0}
      aria-current={isActive ? "true" : undefined}
      className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors group relative cursor-pointer ${
        isActive
          ? "bg-primary/10 border border-primary/20"
          : "hover:bg-muted/30 border border-transparent"
      }`}
    >
      <div className="flex items-start gap-2.5">
        <MessageSquare
          size={14}
          className={`mt-0.5 shrink-0 ${
            isActive ? "text-primary" : "text-muted-foreground/50"
          }`}
        />
        <div className="flex-1 min-w-0">
          <p
            className={`text-[12px] leading-snug truncate ${
              isActive ? "text-foreground font-medium" : "text-foreground/70"
            }`}
          >
            {previewText(conv)}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-muted-foreground/50">
              {formatDate(conv.updatedAt)}
            </span>
            <span className="text-[10px] text-muted-foreground/30">
              {conv.messages.length} msg
            </span>
          </div>
        </div>

        {/* Delete button */}
        <button
          onClick={handleDelete}
          aria-label={
            confirmDelete
              ? "Confirmer la suppression"
              : "Supprimer la conversation"
          }
          className={`shrink-0 w-6 h-6 rounded flex items-center justify-center transition-colors ${
            confirmDelete
              ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
              : "opacity-0 group-hover:opacity-100 text-muted-foreground/40 hover:text-red-400 hover:bg-red-500/10"
          }`}
          title={confirmDelete ? "Cliquer pour confirmer" : "Supprimer"}
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
});

// ── Sidebar Content ─────────────────────────────────────────

interface SidebarContentProps {
  onClose: () => void;
  isMobile: boolean;
}

function SidebarContent({ onClose, isMobile }: SidebarContentProps) {
  const [search, setSearch] = useState("");

  const conversations = useNexusStore((s) => s.conversations);
  const activeConversationId = useNexusStore((s) => s.activeConversationId);
  const addConversation = useNexusStore((s) => s.addConversation);
  const setActiveConversation = useNexusStore((s) => s.setActiveConversation);
  const deleteConversation = useNexusStore((s) => s.deleteConversation);

  const filtered = useMemo(() => {
    const sorted = [...conversations].sort(
      (a, b) => b.updatedAt - a.updatedAt,
    );
    if (!search.trim()) return sorted;
    const q = search.toLowerCase();
    return sorted.filter((c) => {
      const title = c.title?.toLowerCase() || "";
      const firstMsg =
        c.messages.find((m) => m.role === "user")?.content.toLowerCase() || "";
      return title.includes(q) || firstMsg.includes(q);
    });
  }, [conversations, search]);

  const handleSelect = useCallback(
    (id: string) => {
      setActiveConversation(id);
      if (isMobile) onClose();
    },
    [setActiveConversation, isMobile, onClose],
  );

  const handleNew = useCallback(() => {
    addConversation();
    if (isMobile) onClose();
  }, [addConversation, isMobile, onClose]);

  const handleDelete = useCallback(
    (id: string) => {
      deleteConversation(id);
    },
    [deleteConversation],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/10 shrink-0">
        <h2 className="text-[13px] font-semibold text-foreground/80">
          Conversations
        </h2>
        <button
          onClick={onClose}
          aria-label="Fermer le panneau"
          className="w-6 h-6 rounded hover:bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
        >
          {isMobile ? <X size={14} /> : <PanelLeftClose size={14} />}
        </button>
      </div>

      {/* Search + New */}
      <div className="px-3 py-2 space-y-2 shrink-0">
        <div className="relative">
          <Search
            size={12}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher..."
            aria-label="Rechercher une conversation"
            className="w-full pl-7 pr-2 py-1.5 text-[12px] bg-muted/15 border border-border/15 rounded-lg focus-visible:outline-none focus-visible:border-primary/40 placeholder:text-muted-foreground/30"
          />
        </div>
        <Button
          onClick={handleNew}
          variant="outline"
          size="sm"
          className="w-full h-8 text-[11px] gap-1.5 border-border/20 hover:border-primary/30 hover:bg-primary/5"
        >
          <Plus size={12} />
          Nouvelle conversation
        </Button>
      </div>

      {/* List */}
      <ScrollArea className="flex-1">
        <div className="px-2 py-1 space-y-0.5" role="navigation" aria-label="Liste des conversations">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground/40">
              <MessageSquare size={24} className="mb-2" />
              <p className="text-[12px]">
                {search.trim() ? "Aucun resultat" : "Aucune conversation"}
              </p>
            </div>
          ) : (
            filtered.map((conv) => (
              <ConversationItem
                key={conv.id}
                conv={conv}
                isActive={conv.id === activeConversationId}
                onSelect={handleSelect}
                onDelete={handleDelete}
              />
            ))
          )}
        </div>
      </ScrollArea>

      {/* Footer count */}
      <div className="px-3 py-1.5 border-t border-border/10 shrink-0">
        <p className="text-[10px] text-muted-foreground/30 text-center">
          {conversations.length} conversation{conversations.length !== 1 ? "s" : ""}
        </p>
      </div>
    </div>
  );
}

// ── Main Export ──────────────────────────────────────────────

interface ConversationSidebarProps {
  open: boolean;
  onClose: () => void;
}

export function ConversationSidebar({
  open,
  onClose,
}: ConversationSidebarProps) {
  const isMobile = useIsMobile();

  // Desktop: always rendered, visibility toggled via width
  if (!isMobile) {
    return (
      <AnimatePresence initial={false}>
        {open && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="h-full border-r border-border/10 bg-background/60 backdrop-blur-sm overflow-hidden shrink-0"
          >
            <div className="w-[280px] h-full">
              <SidebarContent onClose={onClose} isMobile={false} />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    );
  }

  // Mobile: overlay
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            aria-hidden="true"
          />
          {/* Panel */}
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-y-0 left-0 z-50 w-[280px] bg-background border-r border-border/15 shadow-xl"
          >
            <SidebarContent onClose={onClose} isMobile={true} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
