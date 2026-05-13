// ═══════════════════════════════════════════════════════════════
// NEXUS Web — API Proxy Route
// ═══════════════════════════════════════════════════════════════

import { NextRequest, NextResponse } from "next/server";

const NEXUS_BACKEND = process.env.NEXT_PUBLIC_NEXUS_BACKEND || "http://127.0.0.1:8081";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendPath = path.join("/");
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${NEXUS_BACKEND}/${backendPath}${searchParams ? `?${searchParams}` : ""}`;

  try {
    const res = await fetch(url, {
      headers: {
        ...Object.fromEntries(request.headers.entries()),
        host: new URL(NEXUS_BACKEND).host,
      },
      cache: "no-store",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    return NextResponse.json(
      { detail: `Backend non disponible: ${err instanceof Error ? err.message : "Connection refused"}` },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendPath = path.join("/");
  const url = `${NEXUS_BACKEND}/${backendPath}`;

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
        ...Object.fromEntries(request.headers.entries()),
        host: new URL(NEXUS_BACKEND).host,
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

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    return NextResponse.json(
      { detail: `Backend non disponible: ${err instanceof Error ? err.message : "Connection refused"}` },
      { status: 502 }
    );
  }
}
