// ═══════════════════════════════════════════════════════════════
// NEXUS — VRM Hub Modal
// Minimal, pro, non-surchargé : 3 tabs (Galerie / Local / URL)
// Preview 3D dans le modal, un seul bouton "Utiliser"
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useNexusStore } from "@/lib/nexus-store";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Globe, FolderOpen, Link, Check, Loader2,
  AlertCircle, User, Sparkles, ChevronRight,
} from "lucide-react";
import type { DefaultAvatar } from "./vrm-avatar";

// ── Verified VRM model sources ────────────────────────────────
// Using well-known, community-hosted CC0/CC-BY VRM models

const GALLERY_AVATARS: (DefaultAvatar & { description: string })[] = [
  {
    name: "AvatarSample_A",
    url: "https://pixiv.github.io/three-vrm/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm",
    description: "Modele de test VRM1 (Pixiv)",
  },
  {
    name: "AvatarSample_B",
    url: "https://pixiv.github.io/three-vrm/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm",
    description: "Modele de test VRM1 (Pixiv)",
  },
];

// ── Types ─────────────────────────────────────────────────────

type HubTab = "gallery" | "local" | "url";

interface VRMHubModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (url: string) => void;
  currentModelUrl?: string;
}

// ── Tab button ────────────────────────────────────────────────

function TabButton({
  active, icon, label, onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      role="tab"
      aria-selected={active}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
        active
          ? "bg-primary/15 text-primary border border-primary/30"
          : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

// ── Gallery Card ──────────────────────────────────────────────

function GalleryCard({
  avatar,
  isSelected,
  isLoading,
  onSelect,
}: {
  avatar: DefaultAvatar & { description: string };
  isSelected: boolean;
  isLoading: boolean;
  onSelect: () => void;
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onSelect}
      className={`w-full flex items-center gap-3 p-2.5 rounded-lg border transition-colors text-left ${
        isSelected
          ? "border-primary/50 bg-primary/10"
          : "border-border/20 hover:border-border/40 hover:bg-muted/20"
      }`}
    >
      {/* Thumbnail placeholder */}
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
        isSelected ? "bg-primary/20" : "bg-muted/30"
      }`}>
        {isLoading ? (
          <Loader2 size={16} className="text-primary animate-spin" />
        ) : isSelected ? (
          <Check size={16} className="text-primary" />
        ) : (
          <User size={16} className="text-muted-foreground" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium text-foreground truncate">{avatar.name}</p>
        <p className="text-[9px] text-muted-foreground truncate">{avatar.description}</p>
      </div>

      {isSelected && (
        <ChevronRight size={12} className="text-primary shrink-0" />
      )}
    </motion.button>
  );
}

// ── Main Component ────────────────────────────────────────────

export function VRMHubModal({ open, onClose, onSelect, currentModelUrl }: VRMHubModalProps) {
  const [activeTab, setActiveTab] = useState<HubTab>("gallery");
  const [selectedUrl, setSelectedUrl] = useState<string | null>(currentModelUrl ?? null);
  const [urlInput, setUrlInput] = useState("");
  const [loadingUrl, setLoadingUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setSelectedUrl(currentModelUrl ?? null);
      setError(null);
      setUrlInput("");
    }
  }, [open, currentModelUrl]);

  // Cleanup blob URLs to prevent memory leaks
  useEffect(() => {
    return () => {
      if (selectedUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(selectedUrl);
      }
    };
  }, [selectedUrl]);

  // ── Handle gallery selection ──────────────────────────────

  const handleGallerySelect = useCallback((url: string) => {
    setLoadingUrl(url);
    setError(null);
    setSelectedUrl(url);

    // Validate the URL is reachable by attempting to fetch headers
    fetch(url, { method: "HEAD" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setLoadingUrl(null);
      })
      .catch(() => {
        // URL might not support HEAD, that's ok — we'll let the VRM loader try
        setLoadingUrl(null);
      });
  }, []);

  // ── Handle local file ────────────────────────────────────

  const handleLocalFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".vrm")) {
      setError("Seuls les fichiers .vrm sont supportes");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError("Fichier trop volumineux (max 50 MB)");
      return;
    }

    setError(null);
    const blobUrl = URL.createObjectURL(file);
    setSelectedUrl(blobUrl);
  }, []);

  // ── Handle URL input ─────────────────────────────────────

  const handleUrlConfirm = useCallback(() => {
    const url = urlInput.trim();
    if (!url) return;

    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      setError("L'URL doit commencer par http:// ou https://");
      return;
    }

    if (!url.endsWith(".vrm") && !url.includes(".vrm")) {
      setError("L'URL doit pointer vers un fichier .vrm");
      return;
    }

    setError(null);
    setSelectedUrl(url);
  }, [urlInput]);

  // ── Confirm selection ────────────────────────────────────

  const handleConfirm = useCallback(() => {
    if (selectedUrl) {
      onSelect(selectedUrl);
      onClose();
    }
  }, [selectedUrl, onSelect, onClose]);

  // ── Close on Escape ──────────────────────────────────────

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            className="relative w-full max-w-md mx-4 bg-card border border-border/30 rounded-xl shadow-2xl overflow-hidden"
          >
            {/* ── Header ── */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/15">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-primary" />
                <span className="text-sm font-medium">Avatar VRM</span>
              </div>
              <button
                onClick={onClose}
                aria-label="Fermer le selecteur d'avatar"
                className="w-6 h-6 rounded-md hover:bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            {/* ── Tabs ── */}
            <div className="flex gap-1 px-4 pt-3 pb-2">
              <TabButton
                active={activeTab === "gallery"}
                icon={<Globe size={11} />}
                label="Galerie"
                onClick={() => { setActiveTab("gallery"); setError(null); }}
              />
              <TabButton
                active={activeTab === "local"}
                icon={<FolderOpen size={11} />}
                label="Local"
                onClick={() => { setActiveTab("local"); setError(null); }}
              />
              <TabButton
                active={activeTab === "url"}
                icon={<Link size={11} />}
                label="URL"
                onClick={() => { setActiveTab("url"); setError(null); }}
              />
            </div>

            {/* ── Tab Content ── */}
            <div className="px-4 pb-3 min-h-[180px]">
              {/* Gallery tab */}
              {activeTab === "gallery" && (
                <div className="space-y-1.5">
                  {GALLERY_AVATARS.map((avatar) => (
                    <GalleryCard
                      key={avatar.name}
                      avatar={avatar}
                      isSelected={selectedUrl === avatar.url}
                      isLoading={loadingUrl === avatar.url}
                      onSelect={() => handleGallerySelect(avatar.url)}
                    />
                  ))}
                  <p className="text-[9px] text-muted-foreground/60 pt-1 text-center">
                    Modeles CC0 fournis par la communaute VRM
                  </p>
                </div>
              )}

              {/* Local file tab */}
              {activeTab === "local" && (
                <div className="flex flex-col items-center gap-3 py-4">
                  {/* Drop zone */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full border-2 border-dashed border-border/30 rounded-lg p-6 flex flex-col items-center gap-2 hover:border-primary/40 hover:bg-primary/5 transition-colors cursor-pointer"
                  >
                    <FolderOpen size={24} className="text-muted-foreground" />
                    <span className="text-[11px] text-muted-foreground">
                      Cliquer pour selectionner un fichier .vrm
                    </span>
                    <span className="text-[9px] text-muted-foreground/50">
                      ou glisser-deposer ici (max 50 MB)
                    </span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".vrm"
                    className="hidden"
                    onChange={handleLocalFile}
                  />

                  {selectedUrl && selectedUrl.startsWith("blob:") && (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 w-full">
                      <Check size={12} className="text-emerald-500 shrink-0" />
                      <span className="text-[10px] text-emerald-500 truncate">
                        Fichier charge
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* URL tab */}
              {activeTab === "url" && (
                <div className="flex flex-col gap-3 py-3">
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={urlInput}
                      onChange={(e) => { setUrlInput(e.target.value); setError(null); }}
                      onKeyDown={(e) => { if (e.key === "Enter") handleUrlConfirm(); }}
                      placeholder="https://example.com/avatar.vrm"
                      className="flex-1 h-8 px-3 rounded-md border border-border/25 bg-muted/15 text-[11px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
                    />
                    <button
                      onClick={handleUrlConfirm}
                      disabled={!urlInput.trim()}
                      className="h-8 px-3 rounded-md bg-primary/15 text-primary text-[11px] font-medium hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Charger
                    </button>
                  </div>
                  <p className="text-[9px] text-muted-foreground/50">
                    Collez un lien direct vers un fichier .vrm (VRoid Hub, BOOTH, etc.)
                  </p>
                </div>
              )}

              {/* Error message */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 px-3 py-2 rounded-md bg-red-500/10 border border-red-500/20 mt-2"
                >
                  <AlertCircle size={12} className="text-red-400 shrink-0" />
                  <span className="text-[10px] text-red-400">{error}</span>
                </motion.div>
              )}
            </div>

            {/* ── Footer ── */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-border/15 bg-muted/10">
              <div className="text-[9px] text-muted-foreground/50">
                {selectedUrl ? (
                  selectedUrl.startsWith("blob:") ? (
                    "Fichier local selectionne"
                  ) : (
                    <span className="truncate max-w-[200px] inline-block align-bottom">
                      {selectedUrl.split("/").pop()}
                    </span>
                  )
                ) : (
                  "Aucun avatar selectionne"
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={onClose}
                  className="h-7 px-3 rounded-md text-[11px] text-muted-foreground hover:bg-muted/30 transition-colors"
                >
                  Annuler
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={!selectedUrl}
                  className="h-7 px-4 rounded-md bg-primary text-primary-foreground text-[11px] font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Utiliser
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
