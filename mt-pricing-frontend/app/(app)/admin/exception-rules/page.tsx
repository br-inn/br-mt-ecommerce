import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { ExceptionRulesAdminClient } from "./_client";

/**
 * `/admin/exception-rules` — CRUD de exception rules para gerente/admin.
 *
 * RBAC:
 *  - read  → `prices:read`  (todos los autenticados ven la tabla).
 *  - write → `prices:approve` (gerente/admin) — formulario + activar.
 */
export default function ExceptionRulesAdminPage() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Exception Rules
        </h1>
        <p className="text-sm text-muted-foreground">
          Reglas de excepción que determinan cuándo un precio requiere revisión
          manual. Solo una regla por scope (canal + esquema) puede estar activa.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Reglas activas</CardTitle>
          <CardDescription>
            Umbrales de margen y FX que disparan revisión manual del motor de
            pricing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RbacGuard
            permissions={["prices:read"]}
            fallback={
              <p className="text-sm text-muted-foreground">
                No tienes permisos para ver las exception rules.
              </p>
            }
          >
            <ExceptionRulesAdminClient />
          </RbacGuard>
        </CardContent>
      </Card>
    </div>
  );
}
