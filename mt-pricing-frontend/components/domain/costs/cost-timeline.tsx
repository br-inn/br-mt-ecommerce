"use client";

/**
 * CostTimeline — historia de vigencia de UNA clave de coste (scheme × supplier),
 * renderizada como una línea de tiempo vertical (mock §5 del plan /costos).
 *
 * Cada fila representa un rango `[valid_from, valid_to)` y muestra:
 *   - `valid_from → valid_to` (o "(abierto)" cuando `valid_to` es null),
 *   - `scheme_landed_aed` formateado + moneda AED,
 *   - un `Pill` de estado (Vigente / Programado / Caducado).
 *
 * El estado por fecha se deriva con `costState` (helper compartido en
 * `cost-state.ts`, no se duplica la lógica). La fila Vigente se marca
 * visualmente (punto + borde de acento) siguiendo el patrón de
 * `audit-timeline-rich.tsx`.
 *
 * Componente puramente presentacional: recibe el historial completo (en cualquier
 * orden) por props y lo ordena por `valid_from` ascendente. Sin charting lib.
 */

import * as React from "react";

import { Pill, SectionCard } from "@/components/mt/primitives";
import { MtEmpty } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import type { Cost } from "@/lib/api/endpoints/costs";
import { costState, type CostState } from "@/components/domain/costs/cost-state";

export interface CostTimelineProps {
  /** Historial completo de rangos de UNA clave (scheme × supplier), cualquier orden. */
  costs: Cost[];
  className?: string;
}

const STATE_META: Record<
  CostState,
  { label: string; tone: "success" | "brand" | "ghost" }
> = {
  vigente: { label: "Vigente", tone: "success" },
  programado: { label: "Programado", tone: "brand" },
  caducado: { label: "Caducado", tone: "ghost" },
};

const dateFmt = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

/** Formatea "YYYY-MM-DD" → "01 jun 2026". Solo para display; las comparaciones usan el raw. */
function formatDate(iso: string): string {
  // Construimos en UTC para evitar desfase por timezone al parsear "YYYY-MM-DD".
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return dateFmt.format(d);
}

function formatAed(raw: string | null): string {
  if (raw === null || raw === "") return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return raw;
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function CostTimeline({ costs, className }: CostTimelineProps) {
  const sorted = React.useMemo(
    () => [...costs].sort((a, b) => a.valid_from.localeCompare(b.valid_from)),
    [costs],
  );

  if (sorted.length === 0) {
    return (
      <SectionCard
        title="Línea de tiempo"
        {...(className ? { className } : {})}
      >
        <MtEmpty
          title="Sin rangos de coste"
          hint="Aún no hay historial de vigencia para esta clave."
        />
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Línea de tiempo" {...(className ? { className } : {})}>
      <ol
        className="relative space-y-2 border-l px-4 py-3 pl-7"
        style={{ borderColor: MT.border }}
      >
        {sorted.map((c) => {
          const state = costState(c);
          const meta = STATE_META[state];
          const isCurrent = state === "vigente";
          const dimmed = state === "caducado";
          return (
            <li
              key={c.id}
              className="relative"
              data-testid={`cost-range-${c.id}`}
              data-current={isCurrent ? "true" : "false"}
              style={{ opacity: dimmed ? 0.6 : 1 }}
            >
              <span
                className="absolute -left-[22px] top-2.5 h-2.5 w-2.5 rounded-full border-2"
                style={{
                  background: isCurrent ? MT.success : MT.surface3,
                  borderColor: isCurrent ? MT.success : MT.borderStrong,
                }}
                aria-hidden
              />
              <div
                className="flex flex-wrap items-center gap-3 rounded-md border p-2.5"
                style={{
                  borderColor: isCurrent ? MT.successBorder : MT.border,
                  backgroundColor: isCurrent ? MT.successSoft : MT.surface,
                  ...(isCurrent ? { borderLeftWidth: 3 } : {}),
                }}
              >
                <span
                  className="mt-mono mt-tnum text-[12.5px]"
                  style={{ color: MT.ink }}
                >
                  {formatDate(c.valid_from)} →{" "}
                  {c.valid_to ? (
                    formatDate(c.valid_to)
                  ) : (
                    <span style={{ color: MT.ink3 }}>(abierto)</span>
                  )}
                </span>
                <span
                  className="mt-mono mt-tnum ml-auto text-[12.5px] font-medium"
                  style={{ color: MT.ink }}
                >
                  {formatAed(c.scheme_landed_aed)}{" "}
                  <span
                    className="text-[11px] font-normal"
                    style={{ color: MT.ink3 }}
                  >
                    AED
                  </span>
                </span>
                <Pill tone={meta.tone} dot>
                  {meta.label}
                </Pill>
              </div>
            </li>
          );
        })}
      </ol>
    </SectionCard>
  );
}

export default CostTimeline;
