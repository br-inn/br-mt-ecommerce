import { RbacGuard } from "@/components/auth/rbac-guard";

import { MaterialsAdminClient } from "./_client";

/**
 * `/admin/materials` — CRUD de vocabulario de materiales (Stage 3).
 */
export default function MaterialsAdminPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Materiales</h1>
        <p className="text-sm text-muted-foreground">
          Vocabulario curado de materiales (latón, acero inoxidable, PEX, etc.)
          que se usa en specs y filtros de catálogo.
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
        <MaterialsAdminClient />
      </RbacGuard>
    </div>
  );
}
