// Sentry init — browser side. Tree-shaken si NEXT_PUBLIC_SENTRY_DSN está vacío.
import * as Sentry from "@sentry/nextjs";

import env from "@/lib/env";

const SENSITIVE_HEADERS = new Set(["authorization", "cookie", "x-api-key"]);

export function initSentryClient(): void {
  if (!env.NEXT_PUBLIC_SENTRY_DSN) {
    return;
  }
  Sentry.init({
    dsn: env.NEXT_PUBLIC_SENTRY_DSN,
    // Sample rates conservadores — replays sólo en errores reales.
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.01,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    sendDefaultPii: false,
    beforeSend(event) {
      // Scrub headers sensibles antes de enviar a Sentry.
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

// Auto-init al importar — Next.js lo carga vía instrumentation-client.ts.
initSentryClient();
