import { RbacGuard } from "@/components/auth/rbac-guard";

import { AuditoriaClient } from "./_client";

/**
 * `/auditoria` — Log global de auditoría de cambios en el catálogo.
 *
 * RBAC: `audit:read`
 * Backend: GET /api/v1/audit-events (sin filtro de SKU → todos los eventos)
 */
export default function AuditoriaPage() {
  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Auditoría</h1>
        <p className="text-sm text-muted-foreground">
          Historial de cambios en productos, costos, precios y traducciones
        </p>
      </header>
      <RbacGuard
        permissions={["audit:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permisos para ver este historial. Se requiere el rol{" "}
            <code className="font-mono">audit:read</code>.
          </div>
        }
      >
        <AuditoriaClient />
      </RbacGuard>
    </div>
  );
}
