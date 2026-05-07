"use client";

// Web Vitals reporter — manda métricas Core Web Vitals (CLS/LCP/FID/INP/TTFB)
// a un endpoint interno via sendBeacon. El endpoint puede reenviar a Sentry o
// Better Stack. En dev no reporta para no contaminar las métricas.
import { useReportWebVitals } from "next/web-vitals";

export function WebVitalsReporter(): null {
  useReportWebVitals((metric) => {
    if (process.env.NODE_ENV !== "production") {
      return;
    }
    const body = JSON.stringify(metric);
    // sendBeacon es non-blocking y resiste el unload de la página.
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/web-vitals", body);
      return;
    }
    // Fallback fetch keepalive — para browsers sin sendBeacon.
    void fetch("/api/web-vitals", {
      body,
      method: "POST",
      keepalive: true,
      headers: { "Content-Type": "application/json" },
    });
  });
  return null;
}
