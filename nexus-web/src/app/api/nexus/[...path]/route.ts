import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://127.0.0.1:8081";

async function proxyFetch(url: string, options?: RequestInit) {
  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      ...options,
    });

    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 500), status: res.status };
    }

    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable on ${BACKEND_URL}`, detail: err instanceof Error ? err.message : String(err) },
      { status: 502 }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${BACKEND_URL}/${path.join("/")}${searchParams ? `?${searchParams}` : ""}`;
  return proxyFetch(url);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = `${BACKEND_URL}/${path.join("/")}`;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyFetch(url, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
