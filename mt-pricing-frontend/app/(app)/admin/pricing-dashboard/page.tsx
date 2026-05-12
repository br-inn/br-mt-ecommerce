import type { Metadata } from "next";

import { PricingDashboardClient } from "./_client";

export const metadata: Metadata = {
  title: "Pricing Dashboard | MT Pricing Admin",
  description:
    "Observabilidad del workflow de aprobación de precios: lag, auto-aprobados, exception rules y tendencia 7 días.",
};

/**
 * `/admin/pricing-dashboard` — Dashboard de observabilidad del workflow de
 * aprobación de precios (US-1B-05-07).
 *
 * Cualquier usuario autenticado puede ver las métricas (no requiere permiso
 * específico — el backend valida `get_current_user`).
 */
export default function PricingDashboardPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Pricing Approval Dashboard
        </h1>
        <p className="text-sm text-muted-foreground">
          Observabilidad del workflow de aprobación — lag, auto-aprobados,
          exception rules más activas y tendencia 7 días. Refresca cada 60s.
        </p>
      </header>
      <PricingDashboardClient />
    </div>
  );
}
