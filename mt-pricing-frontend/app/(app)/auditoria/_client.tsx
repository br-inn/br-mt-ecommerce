"use client";

import * as React from "react";
import { AuditTable } from "@/components/domain/audit/audit-table";
import { AuditTimelineRich } from "@/components/domain/audit/audit-timeline-rich";
import { MtButton, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";

const ENTITY_CHIPS = [
  "products",
  "costs",
  "prices",
  "product_translations",
  "fx_rates",
];

const EMPTY_FILTERS = {};

export function AuditoriaClient() {
  const [view, setView] = React.useState<"table" | "timeline">("table");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2
          className="text-[16px] font-semibold tracking-[-0.1px]"
          style={{ color: MT.ink }}
        >
          Auditoría global
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
        <AuditTable baseFilters={EMPTY_FILTERS} entityTypes={ENTITY_CHIPS} />
      ) : (
        <SectionCard
          title="Timeline cronológica"
          subtitle="Histórico de cambios agrupados por día"
        >
          <AuditTimelineRich baseFilters={EMPTY_FILTERS} />
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
