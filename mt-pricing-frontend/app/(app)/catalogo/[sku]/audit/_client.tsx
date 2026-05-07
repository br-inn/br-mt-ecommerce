"use client";

/**
 * Tab "Auditoría" del SKU detail (US-1A-07-03-FE Sprint 4).
 *
 * Reescrita vs el placeholder S2/S3 que usaba `AuditTimeline` directamente:
 *  - Tabla `AuditTable` con filtros multi-entidad (products / costs /
 *    prices / product_translations / fx_rates) — se consultan TODAS las
 *    entidades enlazadas al SKU.
 *  - Toggle vista timeline rica vs tabla densa.
 *  - Filtros base: `entity_id = sku` (el backend resuelve la fan-out por FK
 *    contra costs.sku, prices.product_sku etc.).
 */

import * as React from "react";

import { MtButton, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { AuditTable } from "@/components/domain/audit/audit-table";
import { AuditTimelineRich } from "@/components/domain/audit/audit-timeline-rich";

interface Props {
  sku: string;
}

const ENTITY_CHIPS = [
  "products",
  "costs",
  "prices",
  "product_translations",
  "fx_rates",
];

export function AuditTabClient({ sku }: Props) {
  const [view, setView] = React.useState<"table" | "timeline">("table");

  const baseFilters = React.useMemo(
    () => ({ entity_id: sku }),
    [sku],
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2
          className="text-[16px] font-semibold tracking-[-0.1px]"
          style={{ color: MT.ink }}
        >
          Auditoría · <span className="mt-mono">{sku}</span>
        </h2>
        <div
          className="inline-flex rounded-[5px] border p-0.5"
          style={{ borderColor: MT.border, backgroundColor: MT.surface2 }}
        >
          <ViewTab
            active={view === "table"}
            onClick={() => setView("table")}
            label="Tabla"
          />
          <ViewTab
            active={view === "timeline"}
            onClick={() => setView("timeline")}
            label="Timeline"
          />
        </div>
      </div>

      {view === "table" ? (
        <AuditTable baseFilters={baseFilters} entityTypes={ENTITY_CHIPS} />
      ) : (
        <SectionCard
          title="Timeline cronológica"
          subtitle="Histórico de cambios agrupados por día"
        >
          <AuditTimelineRich baseFilters={baseFilters} />
        </SectionCard>
      )}
    </div>
  );
}

function ViewTab({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <MtButton
      size="sm"
      tone={active ? "primary" : "ghost"}
      onClick={onClick}
      className={active ? "" : "hover:!bg-mt-surface3"}
    >
      {label}
    </MtButton>
  );
}

export default AuditTabClient;
