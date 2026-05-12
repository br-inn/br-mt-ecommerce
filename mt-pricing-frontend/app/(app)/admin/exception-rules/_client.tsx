"use client";

import * as React from "react";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { HistoryDrawer } from "@/components/domain/exception-rules/HistoryDrawer";
import { RuleForm } from "@/components/domain/exception-rules/RuleForm";
import { RuleTable } from "@/components/domain/exception-rules/RuleTable";
import { useExceptionRulesActive } from "@/lib/hooks/exception-rules/use-exception-rules";
import { usePermissions } from "@/lib/hooks/use-permissions";

/**
 * Client component para `/admin/exception-rules`.
 *
 * - Tabla de reglas activas con botón "Activar" (solo gerente/admin).
 * - Formulario para crear nuevas reglas.
 * - Drawer lateral con historial completo.
 */
export function ExceptionRulesAdminClient() {
  const { data, isLoading, isError } = useExceptionRulesActive();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("prices:approve");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data ? `${data.length} regla(s) activa(s)` : "Cargando…"}
        </p>
        <div className="flex items-center gap-2">
          <HistoryDrawer />
          <RbacGuard permissions={["prices:approve"]}>
            <RuleForm />
          </RbacGuard>
        </div>
      </div>

      <RuleTable
        rules={data ?? []}
        isLoading={isLoading}
        isError={isError}
        canManage={canManage}
      />
    </div>
  );
}
