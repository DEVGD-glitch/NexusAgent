// ═══════════════════════════════════════════════════════════════
// NEXUS Web — Shared API proxy helper
// All routes proxy to the FastAPI backend at NEXUS_BACKEND
// ═══════════════════════════════════════════════════════════════

import { NextRequest, NextResponse } from "next/server";

const NEXUS_BACKEND = process.env.NEXT_PUBLIC_NEXUS_BACKEND || "http://127.0.0.1:8081";

function backendUrl(path: string, searchParams?: string): string {
  return `${NEXUS_BACKEND}/${path}${searchParams ? `?${searchParams}` : ""}`;
}

function forwardHeaders(request: NextRequest): Record<string, string> {
  return {
    ...Object.fromEntries(request.headers.entries()),
    host: new URL(NEXUS_BACKEND).host,
  };
}

function errorResponse(err: unknown, status = 502): NextResponse {
  return NextResponse.json(
    { detail: `Backend non disponible: ${err instanceof Error ? err.message : "Connection refused"}` },
    { status }
  );
}

export async function proxyGet(path: string, request: NextRequest): Promise<NextResponse> {
  const searchParams = request.nextUrl.searchParams.toString();
  try {
    const res = await fetch(backendUrl(path, searchParams), {
      headers: forwardHeaders(request),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return errorResponse(err);
  }
}

export async function proxyPost(path: string, request: NextRequest): Promise<NextResponse> {
  try {
    let body: string | null = null;
    try { body = JSON.stringify(await request.json()); } catch { body = null; }
    const res = await fetch(backendUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...forwardHeaders(request) },
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return errorResponse(err);
  }
}

export async function proxyDelete(path: string, request: NextRequest): Promise<NextResponse> {
  try {
    const res = await fetch(backendUrl(path), {
      method: "DELETE",
      headers: forwardHeaders(request),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return errorResponse(err);
  }
}
