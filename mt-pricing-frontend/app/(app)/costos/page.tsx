import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { CostDashboardClient } from "./_client";

/**
 * `/costos` — overview de cobertura de costes por scheme (US-1A-DEV-01 frontend).
 *
 * - Suma productos totales (catalog stats) y, por cada scheme, llama a
 *   `/api/v1/costs/missing` para calcular `covered_pct`.
 * - Permite expandir cada scheme y ver tabla de SKUs faltantes.
 *
 * RBAC: requiere `costs:read` (mismo perms que catalogo costos).
 */
export default async function CostosOverviewPage() {
  const t = await getTranslations("costsDashboard");

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <RbacGuard
        permissions={["costs:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <CostDashboardClient />
      </RbacGuard>
    </div>
  );
}
