"use client";

import * as React from "react";
import { FileText, Layers, Sparkles } from "lucide-react";

import {
  MtButton,
  MtTd,
  MtTh,
  Pill,
  SectionCard,
} from "@/components/mt/primitives";
import { MtEmpty } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import type {
  DatasheetExtractedSpec,
  DatasheetPreviewItem,
  DatasheetsRun,
} from "@/lib/api/endpoints/imports-datasheets";

interface Props {
  run: DatasheetsRun;
  applying: boolean;
  onApply: () => void;
  onBack: () => void;
}

const KIND_LABEL = {
  ficha_tecnica: "Ficha técnica",
  compliance: "Compliance",
  manual: "Manual",
} as const;

/**
 * Preview de una corrida de import de datasheets.
 *
 * UX:
 *  - Header summary con N matched / N orphans + pills tone.
 *  - Por cada item:
 *      · filename + kind detectado + matched_skus pills.
 *      · tabla de specs extraídas con confidence (semáforo).
 *  - Footer: Apply (cobalt) + Volver (ghost).
 *  - Si hay orphans, sección "Orphans" con razón.
 */
export function DatasheetsPreview({ run, applying, onApply, onBack }: Props) {
  const items = run.preview.items;
  const matched = items.filter((i) => i.matched_skus.length > 0);
  const orphans = items.filter((i) => i.matched_skus.length === 0);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryCell label="Total archivos" value={run.preview.total_files} icon={<Layers />} />
        <SummaryCell
          label="Matched"
          value={run.preview.matched}
          tone={run.preview.matched > 0 ? "success" : "neutral"}
          icon={<FileText />}
        />
        <SummaryCell
          label="Orphans"
          value={run.preview.orphans}
          tone={run.preview.orphans > 0 ? "warning" : "neutral"}
          icon={<Sparkles />}
        />
      </div>

      {matched.length > 0 ? (
        <SectionCard
          title="Items matched"
          subtitle="PDFs cuyo sufijo numérico mapea a SKUs existentes"
        >
          <ul className="divide-y" style={{ borderColor: MT.border }}>
            {matched.map((item, idx) => (
              <li className="px-4 py-3" key={`${item.filename}-${idx}`}>
                <DatasheetItemRow item={item} />
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {orphans.length > 0 ? (
        <SectionCard
          title="Orphans"
          subtitle="No se ha podido asociar a ningún SKU"
          actions={
            <Pill tone="warning" dot>
              {orphans.length}
            </Pill>
          }
        >
          <ul className="divide-y" style={{ borderColor: MT.border }}>
            {orphans.map((item, idx) => (
              <li
                className="px-4 py-3 text-[12.5px]"
                key={`${item.filename}-${idx}`}
              >
                <span className="mt-mono font-medium">{item.filename}</span>
                {item.orphan_reason ? (
                  <span
                    className="ml-2 italic"
                    style={{ color: MT.ink3 }}
                  >
                    — {item.orphan_reason}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {items.length === 0 ? (
        <MtEmpty
          title="Sin archivos en la corrida"
          hint="Sube un PDF para empezar."
          icon={<FileText className="size-6" strokeWidth={1.4} />}
        />
      ) : null}

      <div className="flex justify-between">
        <MtButton tone="ghost" onClick={onBack} disabled={applying}>
          Volver
        </MtButton>
        <MtButton
          tone="primary"
          onClick={onApply}
          disabled={applying || matched.length === 0}
          data-testid="datasheets-apply"
        >
          {applying ? "Aplicando…" : `Aplicar (${matched.length})`}
        </MtButton>
      </div>
    </div>
  );
}

function DatasheetItemRow({ item }: { item: DatasheetPreviewItem }) {
  const kindLabel = item.detected_kind
    ? KIND_LABEL[item.detected_kind]
    : "Desconocido";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
        <FileText className="size-3.5" style={{ color: MT.ink4 }} />
        <span className="mt-mono font-medium" style={{ color: MT.ink }}>
          {item.filename}
        </span>
        <Pill tone={item.detected_kind ? "brand" : "neutral"}>{kindLabel}</Pill>
        <span style={{ color: MT.ink3 }}>
          · {item.page_count} páginas · {(item.size_bytes / 1024).toFixed(0)} KB
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
        <span style={{ color: MT.ink3 }}>SKUs:</span>
        {item.matched_skus.map((sku) => (
          <Pill key={sku} tone="success" mono>
            {sku}
          </Pill>
        ))}
      </div>
      {item.extracted_specs.length > 0 ? (
        <details>
          <summary
            className="mt-mono cursor-pointer text-[10.5px] uppercase tracking-[0.5px]"
            style={{ color: MT.brand }}
          >
            Specs extraídas ({item.extracted_specs.length})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <MtTh>Campo</MtTh>
                  <MtTh>Valor</MtTh>
                  <MtTh>Confidence</MtTh>
                  <MtTh>Página</MtTh>
                </tr>
              </thead>
              <tbody>
                {item.extracted_specs.map((spec, i) => (
                  <SpecRow spec={spec} key={`${spec.field}-${i}`} />
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </div>
  );
}

function SpecRow({ spec }: { spec: DatasheetExtractedSpec }) {
  const tone =
    spec.confidence >= 0.85
      ? "success"
      : spec.confidence >= 0.6
        ? "warning"
        : "danger";
  return (
    <tr>
      <MtTd mono>{spec.field}</MtTd>
      <MtTd>{spec.value}</MtTd>
      <MtTd>
        <Pill tone={tone} mono>
          {(spec.confidence * 100).toFixed(0)}%
        </Pill>
      </MtTd>
      <MtTd mono>{spec.source_page ?? "—"}</MtTd>
    </tr>
  );
}

function SummaryCell({
  label,
  value,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: number;
  tone?: "neutral" | "success" | "warning" | "danger";
  icon?: React.ReactNode;
}) {
  const colorMap: Record<string, string> = {
    neutral: MT.ink3,
    success: MT.success,
    warning: MT.warning,
    danger: MT.danger,
  };
  return (
    <div
      className="rounded-lg border px-4 py-3"
      style={{ borderColor: MT.border, backgroundColor: MT.surface }}
    >
      <div
        className="mt-mono text-[10.5px] uppercase tracking-[0.6px]"
        style={{ color: MT.ink3 }}
      >
        {label}
      </div>
      <div className="flex items-center justify-between">
        <span
          className="mt-tnum text-[24px] font-semibold"
          style={{ color: MT.ink }}
        >
          {value}
        </span>
        {icon ? (
          <span style={{ color: colorMap[tone] }}>{icon}</span>
        ) : null}
      </div>
    </div>
  );
}
