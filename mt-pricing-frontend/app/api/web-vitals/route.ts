// Web Vitals ingest endpoint — recibe métricas del browser via sendBeacon.
// TODO Sprint 2: reenvío a Better Stack Logs / Sentry measurements.
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

interface WebVitalMetric {
  id: string;
  name: string;
  value: number;
  rating?: "good" | "needs-improvement" | "poor";
  delta?: number;
  navigationType?: string;
}

export async function POST(request: Request): Promise<Response> {
  try {
    const metric = (await request.json()) as WebVitalMetric;
    // Por ahora sólo logueamos; Sprint 2 reenvía a observabilidad.
    // eslint-disable-next-line no-console
    console.log("[web-vitals]", JSON.stringify(metric));
    return NextResponse.json({ ok: true }, { status: 202 });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "parse-failed" },
      { status: 400 },
    );
  }
}
