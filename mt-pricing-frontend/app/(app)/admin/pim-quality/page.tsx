import { RbacGuard } from "@/components/auth/rbac-guard";

import { PimQualityClient } from "./_client";

/**
 * `/admin/pim-quality` — Dashboard de calidad del catálogo PIM.
 *
 * Muestra un snapshot de los gaps detectados en el catálogo:
 * productos sin nombre EN, sin especificaciones, sin imágenes,
 * sin marca, sin familia y con specs por debajo del umbral mínimo.
 *
 * RBAC:
 *  - read → `admin:read`
 *
 * Backend: GET /api/v1/admin/pim/data-quality
 */
export default function PimQualityPage() {
  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Calidad PIM</h1>
        <p className="text-sm text-muted-foreground">
          Diagnóstico de gaps en el catálogo de productos
        </p>
      </header>
      <RbacGuard
        permissions={["admin:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permisos para ver este reporte. Se requiere el rol{" "}
            <code className="font-mono">admin:read</code>.
          </div>
        }
      >
        <PimQualityClient />
      </RbacGuard>
    </div>
  );
}
