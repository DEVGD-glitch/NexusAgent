import { NextRequest } from "next/server";
import { proxyDelete, proxyGet } from "../../lib/proxy";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyGet(`mcp/${id}`, request);
}
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyDelete(`mcp/${id}`, request);
}
