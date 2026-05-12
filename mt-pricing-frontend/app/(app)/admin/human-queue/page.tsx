import type { Metadata } from "next";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { HumanQueueClient } from "./_client";

export const metadata: Metadata = {
  title: "Cola de Validación Humana | MT Pricing Admin",
  description:
    "Revisión y etiquetado manual de pares candidato-producto MT con baja confianza del calibrador.",
};

/**
 * `/admin/human-queue` — cola de validación humana (US-RND-01-10).
 *
 * Muestra los match candidates con calibrated_confidence < 0.85 para
 * que los operadores los revisen y etiqueten (accept / reject / skip).
 *
 * RBAC:
 *  - read  → `matches:read`
 *  - label → `matches:write`
 */
export default function HumanQueuePage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Cola de Validación Humana
        </h1>
        <p className="text-sm text-muted-foreground">
          Revisión de matches con baja confianza calibrada. Etiqueta cada par
          como Aceptado, Rechazado o Omitido para mejorar el calibrador.
        </p>
      </header>
      <RbacGuard
        permissions={["matches:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permiso para ver la cola de validación humana.
          </div>
        }
      >
        <HumanQueueClient />
      </RbacGuard>
    </div>
  );
}
