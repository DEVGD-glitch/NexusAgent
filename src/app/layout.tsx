// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Root Layout
// ═══════════════════════════════════════════════════════════════

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { ErrorBoundary } from "@/components/nexus/error-boundary";
import { ThemeProvider } from "@/components/nexus/theme-provider";
import { Suspense } from "react";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"] });

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export const metadata: Metadata = {
  title: "NEXUS — Agent IA Souverain",
  description: "Agent IA professionnel souverain — Zero Cloud, Zero Compromis",
};

function LoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        <span className="text-sm text-muted-foreground">Chargement...</span>
      </div>
    </div>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={`${inter.className} antialiased bg-background text-foreground`}>
        <ThemeProvider>
          <ErrorBoundary>
            <Suspense fallback={<LoadingFallback />}>
              {children}
            </Suspense>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  );
}
