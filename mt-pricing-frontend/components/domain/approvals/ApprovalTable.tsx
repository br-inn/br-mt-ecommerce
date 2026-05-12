"use client";

/**
 * ApprovalTable — DataTable con checkboxes, columnas según Pantalla 14.
 *
 * Columnas: checkbox · SKU · canal · esquema · precio · margen · Δ% · alertas · razón excepción · propuesto por · edad (h) · estado
 *
 * US-1B-02-06 · Pantalla 14
 */

import * as React from "react";

import { Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PriceRow, PriceStatus } from "@/lib/api/endpoints/approvals";

// ---- Helpers ---------------------------------------------------------------

const STATUS_TONE: Record<PriceStatus, "success" | "warning" | "danger" | "neutral" | "brand"> = {
  draft: "neutral",
  pending_review: "warning",
  auto_approved: "brand",
  approved: "success",
  rejected: "danger",
  revised: "warning",
  exported: "brand",
  superseded: "neutral",
  migrated: "neutral",
};

const STATUS_LABEL: Record<PriceStatus, string> = {
  draft: "Borrador",
  pending_review: "Pendiente",
  auto_approved: "Auto-aprobado",
  approved: "Aprobado",
  rejected: "Rechazado",
  revised: "Revisado",
  exported: "Exportado",
  superseded: "Reemplazado",
  migrated: "Migrado",
};

function hoursAgo(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 3_600_000);
}

function alertSeverityBadge(alerts: PriceRow["alerts"]) {
  if (alerts.length === 0) return null;
  const hasCritical = alerts.some((a) => a.severity === "critical");
  const hasWarning = alerts.some((a) => a.severity === "warning");
  const tone = hasCritical ? "danger" : hasWarning ? "warning" : "neutral";
  return (
    <Pill tone={tone} dot>
      {alerts.length}
    </Pill>
  );
}

// ---- Props -----------------------------------------------------------------

interface Props {
  items: PriceRow[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: (all: boolean) => void;
  onRowClick: (id: string) => void;
}

// ---- Component -------------------------------------------------------------

export function ApprovalTable({
  items,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onRowClick,
}: Props) {
  const allSelected = items.length > 0 && items.every((r) => selectedIds.has(r.id));
  const someSelected = items.some((r) => selectedIds.has(r.id));

  return (
    <div className="rounded-md border overflow-x-auto" style={{ borderColor: MT.border }}>
      <Table>
        <TableHeader>
          <TableRow>
            {/* Checkbox seleccionar todo */}
            <TableHead className="w-[40px] px-3">
              <input
                type="checkbox"
                className="cursor-pointer"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected && !allSelected;
                }}
                onChange={(e) => onToggleSelectAll(e.target.checked)}
                aria-label="Seleccionar todos"
              />
            </TableHead>
            <TableHead className="min-w-[120px]">SKU</TableHead>
            <TableHead className="w-[90px]">Canal</TableHead>
            <TableHead className="w-[90px]">Esquema</TableHead>
            <TableHead className="w-[100px] text-right">Precio</TableHead>
            <TableHead className="w-[80px] text-right">Margen</TableHead>
            <TableHead className="w-[60px] text-right">Δ%</TableHead>
            <TableHead className="w-[60px] text-center">Alertas</TableHead>
            <TableHead className="min-w-[120px]">Razón excepción</TableHead>
            <TableHead className="w-[100px]">Propuesto por</TableHead>
            <TableHead className="w-[70px] text-right">Edad (h)</TableHead>
            <TableHead className="w-[110px]">Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((row) => {
            const isSelected = selectedIds.has(row.id);
            const hours = hoursAgo(row.created_at);
            const isOld = hours > 48;

            return (
              <TableRow
                key={row.id}
                className={`cursor-pointer ${isSelected ? "bg-blue-50/60" : "hover:bg-muted/30"}`}
                onClick={() => onRowClick(row.id)}
              >
                {/* Checkbox */}
                <TableCell className="px-3" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="cursor-pointer"
                    checked={isSelected}
                    onChange={() => onToggleSelect(row.id)}
                    aria-label={`Seleccionar ${row.product_sku}`}
                  />
                </TableCell>

                {/* SKU */}
                <TableCell>
                  <code className="mt-mono text-[12px] font-medium" style={{ color: MT.ink }}>
                    {row.product_sku}
                  </code>
                </TableCell>

                {/* Canal */}
                <TableCell>
                  <span className="text-xs" style={{ color: MT.ink2 }}>
                    {row.channel_id}
                  </span>
                </TableCell>

                {/* Esquema */}
                <TableCell>
                  <span className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
                    {row.scheme_code}
                  </span>
                </TableCell>

                {/* Precio */}
                <TableCell className="text-right">
                  <span className="mt-mono mt-tnum text-[13px]">
                    {row.amount}{" "}
                    <span className="text-[10px]" style={{ color: MT.ink3 }}>
                      {row.currency}
                    </span>
                  </span>
                </TableCell>

                {/* Margen */}
                <TableCell className="text-right">
                  <span className="mt-mono mt-tnum text-[12px]">
                    {(Number(row.margin_pct) * 100).toFixed(1)}%
                  </span>
                </TableCell>

                {/* Δ% — derivado de breakdown si disponible */}
                <TableCell className="text-right">
                  {(() => {
                    const delta = row.breakdown?.delta_pct;
                    if (delta === undefined || delta === null) return <span style={{ color: MT.ink4 }}>—</span>;
                    const v = Number(delta);
                    const tone = Math.abs(v) > 10 ? "danger" : Math.abs(v) > 5 ? "warning" : "neutral";
                    return (
                      <Pill tone={tone} mono>
                        {v >= 0 ? "+" : ""}{v.toFixed(1)}%
                      </Pill>
                    );
                  })()}
                </TableCell>

                {/* Alertas */}
                <TableCell className="text-center">
                  {alertSeverityBadge(row.alerts) ?? (
                    <span style={{ color: MT.ink4 }}>—</span>
                  )}
                </TableCell>

                {/* Razón excepción */}
                <TableCell>
                  {row.rule_applied ? (
                    <span className="mt-mono text-[11px]" style={{ color: MT.ink2 }}>
                      {row.rule_applied}
                    </span>
                  ) : (
                    <span style={{ color: MT.ink4 }}>—</span>
                  )}
                </TableCell>

                {/* Propuesto por */}
                <TableCell>
                  <span className="text-[11px]" style={{ color: MT.ink3 }}>
                    {row.proposed_by ?? "—"}
                  </span>
                </TableCell>

                {/* Edad */}
                <TableCell className="text-right">
                  <span
                    className="mt-mono mt-tnum text-[12px]"
                    style={{ color: isOld ? MT.warning : MT.ink3 }}
                  >
                    {hours}h
                  </span>
                </TableCell>

                {/* Estado */}
                <TableCell>
                  <Pill tone={STATUS_TONE[row.status]} dot>
                    {STATUS_LABEL[row.status]}
                  </Pill>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
