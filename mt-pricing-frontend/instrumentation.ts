// Next.js 16 instrumentation hook — server-side init.
// Ver https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
import * as Sentry from "@sentry/nextjs";

export async function register(): Promise<void> {
  if (process.env["NEXT_RUNTIME"] === "nodejs") {
    const { initSentryServer } = await import("./lib/sentry/server");
    initSentryServer();
  }
  if (process.env["NEXT_RUNTIME"] === "edge") {
    const { initSentryServer } = await import("./lib/sentry/server");
    initSentryServer();
  }
}

// Capture errors lanzados durante request handling — Next.js 15+ / Sentry SDK v8+.
export const onRequestError = Sentry.captureRequestError;
