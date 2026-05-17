"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import fr from "./fr.json";
import en from "./en.json";

type Locale = "fr" | "en";
type Translations = typeof fr;

const TRANSLATIONS: Record<Locale, Translations> = { fr, en: en as unknown as Translations };

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (typeof current !== "object" || current === null) return path;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : path;
}

export function useTranslations() {
  const [locale, setLocale] = useState<Locale>(() => {
    if (typeof window === "undefined") return "fr";
    const saved = localStorage.getItem("nexus_locale");
    if (saved === "fr" || saved === "en") return saved;
    return navigator.language.startsWith("en") ? "en" : "fr";
  });

  useEffect(() => {
    localStorage.setItem("nexus_locale", locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const t = useCallback(
    (key: string): string => {
      return getNestedValue(TRANSLATIONS[locale] as Record<string, unknown>, key);
    },
    [locale]
  );

  const translations = useMemo(() => TRANSLATIONS[locale], [locale]);

  return { t, locale, setLocale, translations };
}
