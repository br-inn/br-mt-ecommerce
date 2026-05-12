import type { Metadata } from "next";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { ChannelsClient } from "./_client";

export const metadata: Metadata = {
  title: "Canales | MT Pricing Admin",
  description:
    "Consola TI para gestión del ciclo de vida de los canales de venta MT (FSM: inactive → pre_launch → pilot → live → paused → deprecated).",
};

/**
 * `/admin/channels` — consola TI de gestión de canales (US-1B-03-05).
 *
 * Permite a usuarios con rol `ti_integracion` o `admin` ver el estado actual
 * de cada canal y ejecutar transiciones de estado mediante la FSM definida.
 *
 * RBAC:
 *  - read       → `channels:read`  (cualquier usuario con acceso al módulo)
 *  - transition → `channels:manage` (ti_integracion, admin)
 */
export default function ChannelsPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Canales</h1>
        <p className="text-sm text-muted-foreground">
          Gestión del ciclo de vida de canales de venta. Visualiza el estado
          actual y ejecuta transiciones FSM para cada canal.
        </p>
      </header>
      <RbacGuard
        permissions={["channels:read", "channels:manage"]}
        any
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permiso para ver la consola de canales.
          </div>
        }
      >
        <ChannelsClient />
      </RbacGuard>
    </div>
  );
}
