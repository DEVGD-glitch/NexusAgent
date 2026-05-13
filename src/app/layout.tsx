// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Root Layout
// ═══════════════════════════════════════════════════════════════

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"] });

export const metadata: Metadata = {
  title: "NEXUS — Agent IA Souverain",
  description: "Agent IA professionnel souverain — Zero Cloud, Zero Compromis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark">
      <body className={`${inter.className} antialiased bg-background text-foreground`}>
        {children}
      </body>
    </html>
  );
}
