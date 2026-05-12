"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ExceptionRuleRow } from "@/lib/api/endpoints/exception-rules";
import { useActivateExceptionRule } from "@/lib/hooks/exception-rules/use-exception-rules";

interface RuleTableProps {
  rules: ExceptionRuleRow[];
  isLoading?: boolean;
  isError?: boolean;
  canManage?: boolean;
}

/**
 * Tabla de exception rules activas.
 * `canManage` controla si se muestra el botón "Activar" (sólo gerente/admin).
 */
export function RuleTable({
  rules,
  isLoading,
  isError,
  canManage = false,
}: RuleTableProps) {
  const activateMutation = useActivateExceptionRule();

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive">Error al cargar las reglas.</p>
    );
  }

  if (!rules || rules.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        No hay exception rules activas.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Descripción</TableHead>
          <TableHead>Canal</TableHead>
          <TableHead>Esquema</TableHead>
          <TableHead>Umbral margen %</TableHead>
          <TableHead>Umbral FX %</TableHead>
          <TableHead>Margen mín. %</TableHead>
          <TableHead>Versión</TableHead>
          <TableHead>Estado</TableHead>
          {canManage && <TableHead />}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rules.map((r) => (
          <TableRow key={r.id}>
            <TableCell className="font-mono text-xs">{r.code}</TableCell>
            <TableCell className="max-w-xs truncate text-sm">
              {r.description ?? "—"}
            </TableCell>
            <TableCell className="text-xs">{r.channel_id ?? "Global"}</TableCell>
            <TableCell className="text-xs">{r.scheme_code ?? "Todos"}</TableCell>
            <TableCell className="text-right font-mono text-xs">
              {r.margin_threshold_pct != null
                ? `${Number(r.margin_threshold_pct).toFixed(2)}%`
                : "—"}
            </TableCell>
            <TableCell className="text-right font-mono text-xs">
              {r.fx_swing_threshold_pct != null
                ? `${Number(r.fx_swing_threshold_pct).toFixed(2)}%`
                : "—"}
            </TableCell>
            <TableCell className="text-right font-mono text-xs">
              {r.min_margin_pct != null
                ? `${Number(r.min_margin_pct).toFixed(2)}%`
                : "—"}
            </TableCell>
            <TableCell className="text-center text-xs">{r.version}</TableCell>
            <TableCell>
              {r.active ? (
                <Badge variant="default">Activa</Badge>
              ) : (
                <Badge variant="outline">Inactiva</Badge>
              )}
            </TableCell>
            {canManage && (
              <TableCell>
                {!r.active && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={activateMutation.isPending}
                    onClick={() => activateMutation.mutate(r.id)}
                  >
                    Activar
                  </Button>
                )}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
