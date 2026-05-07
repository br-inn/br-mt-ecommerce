// Sentry init — server side (Node + Edge runtime).
import * as Sentry from "@sentry/nextjs";

const SENSITIVE_HEADERS = new Set([
  "authorization",
  "cookie",
  "x-api-key",
  "x-supabase-auth",
]);

export function initSentryServer(): void {
  const dsn = process.env["NEXT_PUBLIC_SENTRY_DSN"] ?? process.env["SENTRY_DSN"];
  if (!dsn) {
    return;
  }
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeSend(event) {
      const headers = event.request?.headers;
      if (headers && typeof headers === "object") {
        for (const key of Object.keys(headers)) {
          if (SENSITIVE_HEADERS.has(key.toLowerCase())) {
            (headers as Record<string, string>)[key] = "***REDACTED***";
          }
        }
      }
      return event;
    },
  });
}
