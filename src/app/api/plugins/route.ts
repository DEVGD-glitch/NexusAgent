// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Plugins API Proxy Route
// ═══════════════════════════════════════════════════════════════

import { NextRequest, NextResponse } from "next/server";

const NEXUS_BACKEND = process.env.NEXT_PUBLIC_NEXUS_BACKEND || "http://127.0.0.1:8081";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${NEXUS_BACKEND}/plugins${searchParams ? `?${searchParams}` : ""}`;

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

export async function POST(request: NextRequest) {
  const url = `${NEXUS_BACKEND}/plugins`;

  try {
    const body = JSON.stringify(await request.json());

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...Object.fromEntries(request.headers.entries()),
        host: new URL(NEXUS_BACKEND).host,
      },
      body,
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
