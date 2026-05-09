import { RbacGuard } from "@/components/auth/rbac-guard";

import { SeriesAdminListClient } from "./_client";

/**
 * `/admin/series` — listado de series con link a detalle (Stage 3 / Wave 11).
 */
export default function SeriesAdminPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Series</h1>
        <p className="text-sm text-muted-foreground">
          Series ricas con tier, presión, banner y traducciones por idioma.
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
        <SeriesAdminListClient />
      </RbacGuard>
    </div>
  );
}
