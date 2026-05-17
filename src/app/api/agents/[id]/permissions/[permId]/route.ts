import { NextRequest } from "next/server";
import { proxyPost } from "../../../../lib/proxy";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string; permId: string }> }) {
  const { id, permId } = await params;
  return proxyPost(`agents/${id}/permissions/${permId}`, request);
}
