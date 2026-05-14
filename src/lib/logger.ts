// ═══════════════════════════════════════════════════════════════
// NEXUS — Structured Logger
// ═══════════════════════════════════════════════════════════════
// Replaces bare console.log/warn/error with a structured logger
// that can be silenced in production or forwarded to a log service.

type LogLevel = "debug" | "info" | "warn" | "error";

interface LogEntry {
  level: LogLevel;
  module: string;
  message: string;
  data?: unknown;
  timestamp: string;
}

const IS_PROD = process.env.NODE_ENV === "production";

function formatEntry(entry: LogEntry): string {
  return `[${entry.timestamp}] ${entry.level.toUpperCase()} [${entry.module}] ${entry.message}`;
}

function emit(level: LogLevel, module: string, message: string, data?: unknown): void {
  // In production, suppress debug and info
  if (IS_PROD && (level === "debug" || level === "info")) return;

  const entry: LogEntry = {
    level,
    module,
    message,
    data,
    timestamp: new Date().toISOString(),
  };

  const formatted = formatEntry(entry);

  switch (level) {
    case "debug":
      // eslint-disable-next-line no-console
      if (data !== undefined) console.debug(formatted, data);
      else console.debug(formatted);
      break;
    case "info":
      // eslint-disable-next-line no-console
      if (data !== undefined) console.info(formatted, data);
      else console.info(formatted);
      break;
    case "warn":
      // eslint-disable-next-line no-console
      if (data !== undefined) console.warn(formatted, data);
      else console.warn(formatted);
      break;
    case "error":
      // eslint-disable-next-line no-console
      if (data !== undefined) console.error(formatted, data);
      else console.error(formatted);
      break;
  }
}

/**
 * Create a scoped logger for a module.
 *
 * Usage:
 *   const log = createLogger("ChatView");
 *   log.info("Message sent");
 *   log.error("Failed to send", error);
 */
export function createLogger(module: string) {
  return {
    debug: (msg: string, data?: unknown) => emit("debug", module, msg, data),
    info: (msg: string, data?: unknown) => emit("info", module, msg, data),
    warn: (msg: string, data?: unknown) => emit("warn", module, msg, data),
    error: (msg: string, data?: unknown) => emit("error", module, msg, data),
  };
}
