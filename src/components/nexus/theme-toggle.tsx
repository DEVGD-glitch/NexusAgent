// ═══════════════════════════════════════════════════════════════
// NEXUS — Theme Toggle Button (cycles dark → light → system)
// ═══════════════════════════════════════════════════════════════

"use client";

import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "./theme-provider";

const THEME_ORDER = ["dark", "light", "system"] as const;

const THEME_META = {
  dark: { icon: Moon, label: "Sombre" },
  light: { icon: Sun, label: "Clair" },
  system: { icon: Monitor, label: "Systeme" },
} as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const cycle = () => {
    const idx = THEME_ORDER.indexOf(theme);
    const next = THEME_ORDER[(idx + 1) % THEME_ORDER.length];
    setTheme(next);
  };

  const { icon: Icon, label } = THEME_META[theme];

  return (
    <button
      onClick={cycle}
      aria-label={`Theme actuel : ${label}. Cliquer pour changer.`}
      className="flex items-center gap-1.5 px-2 py-1 rounded-md border border-border/15 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors"
    >
      <Icon size={11} />
      <span>{label}</span>
    </button>
  );
}
