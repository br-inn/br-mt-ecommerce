import type { Metadata } from "next";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { ErpEventosClient } from "./_client";

export const metadata: Metadata = {
  title: "ERP Sync Events | MT Pricing Admin",
  description:
    "Log de eventos ERP salientes (outbox pattern). Visualización y reintento de eventos fallidos.",
};

/**
 * `/admin/erp-eventos` — log de eventos ERP salientes (US-INV-01-07).
 *
 * Muestra la tabla `erp_sync_events` clasificada por estado:
 * Pendientes / Entregados / Fallidos / Omitidos.
 *
 * RBAC: solo rol `admin`.
 */
export default function ErpEventosPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          ERP Sync Events
        </h1>
        <p className="text-sm text-muted-foreground">
          Log de eventos salientes hacia el ERP externo (outbox pattern).
          Los eventos fallidos pueden reintentarse manualmente.
        </p>
      </header>
      <RbacGuard
        permissions={["admin"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permiso para ver el log de eventos ERP. Se requiere rol admin.
          </div>
        }
      >
        <ErpEventosClient />
      </RbacGuard>
    </div>
  );
}
