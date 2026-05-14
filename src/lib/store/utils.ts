// ═══════════════════════════════════════════════════════════════
// NEXUS — Store Utilities
// ═══════════════════════════════════════════════════════════════

export function uid(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
}
