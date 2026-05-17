import { NextRequest } from "next/server";
import { proxyGet, proxyPost } from "../lib/proxy";

export async function GET(request: NextRequest) { return proxyGet("mcp", request); }
export async function POST(request: NextRequest) { return proxyPost("mcp/install", request); }
