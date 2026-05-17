// ═══════════════════════════════════════════════════════════════
// NEXUS Web — API Proxy Route
// ═══════════════════════════════════════════════════════════════

import { NextRequest, NextResponse } from "next/server";

const NEXUS_BACKEND = process.env.NEXT_PUBLIC_NEXUS_BACKEND || "http://127.0.0.1:8081";

// Allowed backend path prefixes (allowlist for SSRF protection)
const ALLOWED_PATH_PREFIXES = [
  "chat",
  "run",
  "health",
  "status",
  "providers",
  "models",
  "memory",
  "agents",
  "skills",
  "workflows",
  "mcp",
  "plugins",
  "monitoring",
  "metrics",
  "eval",
  "context7",
  "voice",
  "cron",
  "sandbox",
  "audit",
  "tts",
  "stt",
  "config",
];

// Headers that should NOT be forwarded to the backend (security)
const BLOCKED_HEADERS = new Set([
  "cookie",
  "authorization",
  "host",
  "origin",
  "referer",
  "x-forwarded-for",
  "x-real-ip",
  "x-forwarded-proto",
  "x-forwarded-host",
]);

function filterHeaders(headers: Headers): Record<string, string> {
  const filtered: Record<string, string> = {};
  headers.forEach((value, key) => {
    if (!BLOCKED_HEADERS.has(key.toLowerCase())) {
      filtered[key] = value;
    }
  });
  return filtered;
}

function validatePath(pathSegments: string[]): string | null {
  if (pathSegments.length === 0) return null;

  // Block path traversal attempts
  for (const segment of pathSegments) {
    if (segment.includes("..") || segment.includes("\\") || segment.startsWith("/")) {
      return null;
    }
  }

  // Check first segment against allowlist
  const firstSegment = pathSegments[0].toLowerCase();
  if (!ALLOWED_PATH_PREFIXES.includes(firstSegment)) {
    return null;
  }

  return pathSegments.join("/");
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendPath = validatePath(path);

  if (!backendPath) {
    return NextResponse.json(
      { detail: "Chemin non autorisé" },
      { status: 403 }
    );
  }

  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${NEXUS_BACKEND}/${backendPath}${searchParams ? `?${searchParams}` : ""}`;

  try {
    const res = await fetch(url, {
      headers: filterHeaders(request.headers),
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    // Non-JSON responses (files, etc.)
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { detail: "Backend non disponible" },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendPath = validatePath(path);

  if (!backendPath) {
    return NextResponse.json(
      { detail: "Chemin non autorisé" },
      { status: 403 }
    );
  }

  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${NEXUS_BACKEND}/${backendPath}${searchParams ? `?${searchParams}` : ""}`;

  try {
    let body: string | null = null;
    try {
      body = JSON.stringify(await request.json());
    } catch {
      body = null;
    }

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...filterHeaders(request.headers),
      },
      body,
    });

    // Handle SSE streaming
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      const stream = res.body;
      if (!stream) {
        return NextResponse.json({ detail: "Stream vide" }, { status: 502 });
      }

      return new NextResponse(stream, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    if (contentType.includes("application/json")) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    const bodyText = await res.text();
    return new NextResponse(bodyText, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { detail: "Backend non disponible" },
      { status: 502 }
    );
  }
}
