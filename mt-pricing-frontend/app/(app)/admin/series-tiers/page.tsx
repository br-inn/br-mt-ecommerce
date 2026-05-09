import { RbacGuard } from "@/components/auth/rbac-guard";

import { SeriesTiersAdminClient } from "./_client";

/**
 * `/admin/series-tiers` — CRUD del vocabulario cerrado de tiers de serie
 * (PLATINUM, GOLD, SILVER, BRONZE…).
 */
export default function SeriesTiersAdminPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Tiers de serie</h1>
        <p className="text-sm text-muted-foreground">
          Vocabulario cerrado para clasificar la calidad/posicionamiento de
          cada serie (PLATINUM, GOLD, SILVER…).
        </p>
      </header>
      <RbacGuard
        permissions={["admin:taxonomy"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permisos para administrar la taxonomía.
          </div>
        }
      >
        <SeriesTiersAdminClient />
      </RbacGuard>
    </div>
  );
}
