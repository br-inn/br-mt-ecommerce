import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TIMEOUT_MS = 3000;

export async function GET() {
  const backend = process.env["NEXT_PUBLIC_BACKEND_URL"];
  if (!backend) {
    return NextResponse.json(
      { status: "degraded", reason: "NEXT_PUBLIC_BACKEND_URL not set" },
      { status: 503 },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(`${backend}/health/ready`, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    if (!response.ok) {
      return NextResponse.json(
        { status: "unhealthy", upstream: response.status },
        { status: 503 },
      );
    }
    return NextResponse.json({ status: "ok" }, { status: 200 });
  } catch (error) {
    clearTimeout(timer);
    return NextResponse.json(
      {
        status: "unhealthy",
        error: error instanceof Error ? error.message : "unknown",
      },
      { status: 503 },
    );
  }
}
