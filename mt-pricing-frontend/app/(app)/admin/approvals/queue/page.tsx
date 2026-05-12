import type { Metadata } from "next";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { ApprovalQueueClient } from "./_client";

export const metadata: Metadata = {
  title: "Cola de Aprobación | MT Pricing Admin",
  description:
    "Revisión y aprobación de propuestas de precio en estado pending_review. Bulk-approve, reject con comentario y drawer de detalle.",
};

/**
 * `/admin/approvals/queue` — Cola de aprobación de precios (US-1B-02-06).
 *
 * Muestra propuestas en `pending_review` para que el Gerente Comercial
 * las apruebe, rechace o revise individualmente o en bulk.
 *
 * RBAC:
 *  - read  → `prices:read`
 *  - write → `prices:approve`
 */
export default function ApprovalQueuePage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Cola de Aprobación
        </h1>
        <p className="text-sm text-muted-foreground">
          Propuestas de precio pendientes de revisión. Aprueba, rechaza o revisa
          individualmente o en lote.
        </p>
      </header>
      <RbacGuard
        permissions={["prices:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permiso para ver la cola de aprobación.
          </div>
        }
      >
        <ApprovalQueueClient />
      </RbacGuard>
    </div>
  );
}
