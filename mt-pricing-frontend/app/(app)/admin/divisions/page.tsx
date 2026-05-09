import { RbacGuard } from "@/components/auth/rbac-guard";

import { DivisionsAdminClient } from "./_client";

/**
 * `/admin/divisions` — CRUD de divisiones (Stage 3 / Wave 11).
 *
 * RBAC:
 *  - read  → `admin:taxonomy`
 *  - write → `admin:taxonomy`
 */
export default function DivisionsAdminPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Divisiones</h1>
        <p className="text-sm text-muted-foreground">
          Hidrosanitario, industrial, gas, minero, etc. Cada producto puede
          pertenecer a varias divisiones.
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
        <DivisionsAdminClient />
      </RbacGuard>
    </div>
  );
}
