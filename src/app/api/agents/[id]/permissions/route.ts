import { NextRequest } from "next/server";
import { proxyGet, proxyPost } from "../../../lib/proxy";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyGet(`agents/${id}/permissions`, request);
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyPost(`agents/${id}/permissions`, request);
}
