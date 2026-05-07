"use client";

import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { MtTd, MtTh, Pill, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { PriceDetail, PriceStatus } from "@/lib/api/endpoints/pricing";

interface Props {
  price: PriceDetail;
  className?: string;
}

const STATUS_TONE: Record<
  PriceStatus,
  "success" | "warning" | "danger" | "neutral" | "brand"
> = {
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
  pending_review: "Pendiente revisión",
  auto_approved: "Auto-aprobado",
  approved: "Aprobado",
  rejected: "Rechazado",
  revised: "Revisado",
  exported: "Exportado",
  superseded: "Reemplazado",
  migrated: "Migrado",
};

/**
 * Card de detalle de propuesta — amounts + breakdown JSON expandible.
 *
 * Notas UX:
 *  - Header muestra SKU · scheme · status pill (semáforo MT).
 *  - Bloque amounts en mt-mono mt-tnum (números densos, alineación tabular).
 *  - Breakdown formateado como tabla key/value para top-level + JSON collapsible
 *    para nested (más legible que pre raw).
 */
export function PricingDetailCard({ price, className }: Props) {
  return (
    <SectionCard
      title={
        <span className="flex items-center gap-2">
          <span className="mt-mono">{price.product_sku}</span>
          <span style={{ color: MT.ink3 }}>·</span>
          <span className="mt-mono text-[12px]" style={{ color: MT.ink3 }}>
            {price.scheme_code}
          </span>
        </span>
      }
      subtitle={`Creada ${new Date(price.created_at).toLocaleString()}`}
      actions={<Pill tone={STATUS_TONE[price.status]} dot>{STATUS_LABEL[price.status]}</Pill>}
      {...(className ? { className } : {})}
    >
      <div className="grid gap-3 px-4 py-3 md:grid-cols-2">
        <KvRow label="Importe">
          <span className="mt-mono mt-tnum text-[18px] font-semibold">
            {price.amount}{" "}
            <span className="text-[12px] font-normal" style={{ color: MT.ink3 }}>
              {price.currency}
            </span>
          </span>
        </KvRow>
        <KvRow label="PVP_min">
          <span className="mt-mono mt-tnum">{price.pvp_min ?? "—"}</span>
        </KvRow>
        <KvRow label="Margen">
          <span className="mt-mono mt-tnum">
            {(Number(price.margin_pct) * 100).toFixed(2)}%
          </span>
        </KvRow>
        <KvRow label="Regla aplicada">
          <span className="mt-mono text-[12px]">{price.rule_applied ?? "—"}</span>
        </KvRow>
        <KvRow label="Fórmula">
          <code
            className="mt-mono break-all text-[11px]"
            style={{ color: MT.ink2 }}
          >
            {price.formula ?? "—"}
          </code>
        </KvRow>
        <KvRow label="Vigente desde">
          <span className="mt-mono text-[12px]">
            {new Date(price.valid_from).toLocaleString()}
          </span>
        </KvRow>
      </div>

      <div className="border-t" style={{ borderColor: MT.border }}>
        <BreakdownBlock breakdown={price.breakdown} />
      </div>
    </SectionCard>
  );
}

function KvRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
        style={{ color: MT.ink3 }}
      >
        {label}
      </span>
      {children}
    </div>
  );
}

function BreakdownBlock({
  breakdown,
}: {
  breakdown: Record<string, unknown>;
}) {
  const [open, setOpen] = React.useState(true);

  const entries = Object.entries(breakdown);
  if (entries.length === 0) {
    return (
      <div
        className="px-4 py-3 text-[12px]"
        style={{ color: MT.ink3 }}
      >
        Sin desglose disponible.
      </div>
    );
  }

  return (
    <div className="px-4 py-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[12px] font-medium"
        style={{ color: MT.ink2 }}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="size-3.5" />
        ) : (
          <ChevronRight className="size-3.5" />
        )}
        <span className="mt-mono uppercase tracking-[0.5px] text-[10.5px]">
          Breakdown · {entries.length}
        </span>
      </button>

      {open ? (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-separate border-spacing-0">
            <thead>
              <tr>
                <MtTh>Componente</MtTh>
                <MtTh className="text-right">Valor</MtTh>
              </tr>
            </thead>
            <tbody>
              {entries.map(([key, value]) => {
                const isPrimitive =
                  value === null ||
                  typeof value === "string" ||
                  typeof value === "number" ||
                  typeof value === "boolean";
                return (
                  <tr key={key}>
                    <MtTd mono>{key}</MtTd>
                    <MtTd mono className="text-right">
                      {isPrimitive ? (
                        String(value)
                      ) : (
                        <details>
                          <summary
                            className="cursor-pointer text-[11px]"
                            style={{ color: MT.brand }}
                          >
                            ver objeto
                          </summary>
                          <pre className="mt-1 text-left text-[10.5px] leading-tight">
                            {JSON.stringify(value, null, 2)}
                          </pre>
                        </details>
                      )}
                    </MtTd>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
