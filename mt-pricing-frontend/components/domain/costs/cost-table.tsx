"use client";

/**
 * CostTable — tabla por (scheme × supplier) para US-1A-04-04 AC#1.
 *
 * Contrato de vigencia por rangos (Task 2):
 * Columnas: Scheme · Supplier · Currency origin · Total AED landed · FX rate
 *           · Desde (valid_from) · Hasta (valid_to) · Estado · Acciones.
 *
 * - El "Estado" es un badge derivado por FECHA respecto a hoy:
 *     Vigente   → hoy ∈ [valid_from, valid_to] (o valid_to null & valid_from ≤ hoy)
 *     Programado → valid_from > hoy
 *     Caducado  → valid_to < hoy
 * - Click en row expande breakdown JSONB con cada componente desglosado (AC#2).
 * - Toggle "Mostrar histórico" muestra/oculta rangos no vigentes (AC#4).
 *
 * Estilo: primitivos `components/mt`. Las acciones (editar / descatalogar) las
 * lleva el caller — recibimos `onEdit(cost)`, `onClose(cost)` y `onAdd()`.
 */

import * as React from "react";
import { ChevronDown, ChevronRight, Pencil, Plus, Ban } from "lucide-react";

import { MtButton, MtTd, MtTh, Pill, SectionCard } from "@/components/mt/primitives";
import { MtEmpty, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import type { Cost } from "@/lib/api/endpoints/costs";

export interface CostTableProps {
  costs: Cost[];
  loading?: boolean;
  onEdit?: (cost: Cost) => void;
  /** Descatalogar / cerrar el rango vigente (fija valid_to). */
  onClose?: (cost: Cost) => void;
  onAdd?: () => void;
  /** Si true, se muestran también los rangos no vigentes (caducados/programados). */
  showHistory?: boolean;
  onToggleHistory?: (next: boolean) => void;
  canWrite?: boolean;
}

type CostState = "vigente" | "programado" | "caducado";

/** Hoy en formato "YYYY-MM-DD" (local), comparable lexicográficamente con las dates ISO. */
function todayIso(): string {
  return new Date().toLocaleDateString("en-CA"); // en-CA → "YYYY-MM-DD"
}

/** Estado del coste derivado por fecha respecto a hoy. */
export function costState(cost: Pick<Cost, "valid_from" | "valid_to">): CostState {
  const today = todayIso();
  if (cost.valid_from > today) return "programado";
  if (cost.valid_to && cost.valid_to < today) return "caducado";
  return "vigente";
}

const STATE_META: Record<
  CostState,
  { label: string; tone: "success" | "brand" | "ghost" }
> = {
  vigente: { label: "Vigente", tone: "success" },
  programado: { label: "Programado", tone: "brand" },
  caducado: { label: "Caducado", tone: "ghost" },
};

function formatNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  const n = typeof raw === "string" ? Number(raw) : raw;
  if (!Number.isFinite(n)) return String(raw);
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export function CostTable({
  costs,
  loading = false,
  onEdit,
  onClose,
  onAdd,
  showHistory = false,
  onToggleHistory,
  canWrite = true,
}: CostTableProps) {
  const visibleCosts = React.useMemo(
    () =>
      showHistory ? costs : costs.filter((c) => costState(c) === "vigente"),
    [costs, showHistory],
  );
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const headerActions = (
    <>
      {onToggleHistory ? (
        <MtButton
          size="sm"
          tone={showHistory ? "primary" : "ghost"}
          onClick={() => onToggleHistory(!showHistory)}
          data-testid="costs-toggle-history"
        >
          {showHistory ? "Ocultar histórico" : "Mostrar histórico"}
        </MtButton>
      ) : null}
      {canWrite && onAdd ? (
        <MtButton
          size="sm"
          tone="primary"
          icon={<Plus className="size-3" />}
          onClick={onAdd}
          data-testid="costs-add"
        >
          Añadir coste
        </MtButton>
      ) : null}
    </>
  );

  if (loading) {
    return (
      <SectionCard title="Costes por esquema" actions={headerActions}>
        <div className="flex flex-col gap-2 p-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <MtSkeleton key={i} width="100%" height={28} />
          ))}
        </div>
      </SectionCard>
    );
  }

  if (visibleCosts.length === 0) {
    return (
      <SectionCard title="Costes por esquema" actions={headerActions}>
        <MtEmpty
          title="Sin costes registrados"
          hint={
            canWrite
              ? "Pulsa “Añadir coste” para crear el primer scheme."
              : "Pide a un Comercial que registre costes para este SKU."
          }
        />
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Costes por esquema" actions={headerActions}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0">
          <thead>
            <tr>
              <MtTh className="w-[28px]" />
              <MtTh>Scheme</MtTh>
              <MtTh>Supplier</MtTh>
              <MtTh>Origen</MtTh>
              <MtTh className="text-right">Total AED landed</MtTh>
              <MtTh>FX</MtTh>
              <MtTh>Desde</MtTh>
              <MtTh>Hasta</MtTh>
              <MtTh>Estado</MtTh>
              {canWrite ? <MtTh className="text-right">Acción</MtTh> : null}
            </tr>
          </thead>
          <tbody>
            {visibleCosts.map((c) => {
              const isOpen = expanded.has(c.id);
              const state = costState(c);
              const meta = STATE_META[state];
              const dimmed = state !== "vigente";
              return (
                <React.Fragment key={c.id}>
                  <tr
                    style={{ opacity: dimmed ? 0.55 : 1 }}
                    data-testid={`cost-row-${c.id}`}
                  >
                    <MtTd>
                      <button
                        type="button"
                        onClick={() => toggle(c.id)}
                        aria-expanded={isOpen}
                        aria-label={isOpen ? "Colapsar" : "Expandir"}
                        className="rounded p-1 hover:bg-mt-surface3"
                        data-testid={`cost-toggle-${c.id}`}
                      >
                        {isOpen ? (
                          <ChevronDown className="size-3.5" />
                        ) : (
                          <ChevronRight className="size-3.5" />
                        )}
                      </button>
                    </MtTd>
                    <MtTd mono className="font-medium">
                      {c.scheme_code}
                    </MtTd>
                    <MtTd>{c.supplier_code ?? "—"}</MtTd>
                    <MtTd mono>{c.currency_origin}</MtTd>
                    <MtTd mono className="text-right">
                      {formatNumber(c.scheme_landed_aed)}
                    </MtTd>
                    <MtTd mono>
                      {c.fx_rate_id ? (
                        <span title={c.fx_rate_id}>as-of</span>
                      ) : (
                        <Pill tone="neutral">identity</Pill>
                      )}
                      {c.fx_inferred ? (
                        <Pill tone="warning" className="ml-1">
                          inferred
                        </Pill>
                      ) : null}
                    </MtTd>
                    <MtTd mono>{formatDate(c.valid_from)}</MtTd>
                    <MtTd mono>
                      {c.valid_to ? (
                        formatDate(c.valid_to)
                      ) : (
                        <span style={{ color: MT.ink3 }}>abierto</span>
                      )}
                    </MtTd>
                    <MtTd>
                      <Pill tone={meta.tone} dot>
                        {meta.label}
                      </Pill>
                    </MtTd>
                    {canWrite ? (
                      <MtTd className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {state !== "caducado" && onEdit ? (
                            <MtButton
                              size="sm"
                              tone="ghost"
                              icon={<Pencil className="size-3" />}
                              onClick={() => onEdit(c)}
                              aria-label="edit"
                              data-testid={`cost-edit-${c.id}`}
                            >
                              Corregir
                            </MtButton>
                          ) : null}
                          {state === "vigente" && onClose ? (
                            <MtButton
                              size="sm"
                              tone="ghost"
                              icon={<Ban className="size-3" />}
                              onClick={() => onClose(c)}
                              aria-label="descatalogar"
                              data-testid={`cost-close-${c.id}`}
                            >
                              Descatalogar
                            </MtButton>
                          ) : null}
                        </div>
                      </MtTd>
                    ) : null}
                  </tr>
                  {isOpen ? (
                    <tr
                      data-testid={`cost-breakdown-${c.id}`}
                      style={{ backgroundColor: MT.surface2 }}
                    >
                      <MtTd colSpan={canWrite ? 10 : 9}>
                        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 md:grid-cols-3">
                          {Object.entries(c.breakdown ?? {}).map(([k, v]) => (
                            <div
                              key={k}
                              className="flex items-center justify-between rounded-[4px] border px-2 py-1"
                              style={{
                                borderColor: MT.border,
                                backgroundColor: MT.surface,
                              }}
                            >
                              <span
                                className="mt-mono text-[11.5px]"
                                style={{ color: MT.ink3 }}
                              >
                                {k}
                              </span>
                              <span
                                className="mt-mono mt-tnum text-[12.5px]"
                                style={{ color: MT.ink }}
                              >
                                {formatNumber(v as number | string | null)}
                              </span>
                            </div>
                          ))}
                          {Object.keys(c.breakdown ?? {}).length === 0 ? (
                            <span
                              className="text-[12px]"
                              style={{ color: MT.ink3 }}
                            >
                              Sin componentes desglosados.
                            </span>
                          ) : null}
                        </div>
                      </MtTd>
                    </tr>
                  ) : null}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

export default CostTable;
