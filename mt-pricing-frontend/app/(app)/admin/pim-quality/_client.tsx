"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertCircle,
  BarChart2,
  Image,
  Languages,
  ListChecks,
  RefreshCw,
  Tag,
  Tags,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { usePimDataQuality } from "@/lib/hooks/admin/use-pim-quality";
import type { PimDataQualityReport, PimGap } from "@/lib/api/endpoints/admin-pim";

// ---------------------------------------------------------------------------
// Utilidad: tiempo relativo sin dependencias externas
// ---------------------------------------------------------------------------

const RTF = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

function timeAgo(isoDate: string): string {
  const diffMs = new Date(isoDate).getTime() - Date.now();
  const diffSec = Math.round(diffMs / 1_000);
  const diffMin = Math.round(diffSec / 60);
  const diffHr = Math.round(diffMin / 60);
  const diffDay = Math.round(diffHr / 24);

  if (Math.abs(diffSec) < 60) return RTF.format(diffSec, "second");
  if (Math.abs(diffMin) < 60) return RTF.format(diffMin, "minute");
  if (Math.abs(diffHr) < 24) return RTF.format(diffHr, "hour");
  return RTF.format(diffDay, "day");
}

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

interface GapCardDef {
  key: keyof PimDataQualityReport["gaps"];
  label: string;
  icon: React.ReactNode;
}

const GAP_CARDS: GapCardDef[] = [
  {
    key: "missing_name_en",
    label: "Sin nombre EN",
    icon: <Languages className="size-4" />,
  },
  {
    key: "missing_specs",
    label: "Sin especificaciones",
    icon: <ListChecks className="size-4" />,
  },
  {
    key: "missing_images",
    label: "Sin imágenes",
    icon: <Image className="size-4" />,
  },
  {
    key: "missing_brand",
    label: "Sin marca",
    icon: <Tag className="size-4" />,
  },
  {
    key: "missing_family",
    label: "Sin familia",
    icon: <Tags className="size-4" />,
  },
  {
    key: "specs_below_threshold",
    label: "Specs incompletas (< 3 campos)",
    icon: <AlertCircle className="size-4" />,
  },
];

// ---------------------------------------------------------------------------
// Severidad visual por pct
// ---------------------------------------------------------------------------

interface SeverityColors {
  bar: string;
  badge: string;
  badgeBg: string;
}

function severityColors(pct: number): SeverityColors {
  if (pct < 2) {
    return { bar: MT.success, badge: MT.success, badgeBg: MT.successSoft };
  }
  if (pct < 10) {
    return { bar: MT.warning, badge: MT.warning, badgeBg: MT.warningSoft };
  }
  return { bar: MT.danger, badge: MT.danger, badgeBg: MT.dangerSoft };
}

// ---------------------------------------------------------------------------
// Componente de tarjeta individual
// ---------------------------------------------------------------------------

function GapCard({ def, gap }: { def: GapCardDef; gap: PimGap }) {
  const colors = severityColors(gap.pct);
  const samples = (gap.sample_skus ?? []).slice(0, 5);

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <span
            className="grid size-7 shrink-0 place-items-center rounded-md"
            style={{ background: colors.badgeBg, color: colors.badge }}
          >
            {def.icon}
          </span>
          {def.label}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {/* Número grande + pct */}
        <div className="flex items-end gap-2">
          <span
            className="text-3xl font-bold tabular-nums leading-none"
            style={{ color: colors.badge }}
          >
            {gap.count}
          </span>
          <span className="mb-0.5 text-xs" style={{ color: MT.ink3 }}>
            {gap.pct.toFixed(1)}%
          </span>
        </div>

        {/* Barra de progreso */}
        <div
          className="h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: MT.surface3 }}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(gap.pct, 100)}%`,
              background: colors.bar,
            }}
          />
        </div>

        {/* Sample SKUs */}
        {samples.length > 0 ? (
          <ul className="mt-1 space-y-0.5">
            {samples.map((sku) => (
              <li key={sku}>
                <Link
                  href={`/catalogo/${encodeURIComponent(sku)}`}
                  className="truncate text-[11px] underline-offset-2 hover:underline"
                  style={{ color: MT.brand }}
                >
                  {sku}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[11px]" style={{ color: MT.ink4 }}>
            Sin productos afectados
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Componente principal exportado
// ---------------------------------------------------------------------------

export function PimQualityClient() {
  const { data, isLoading, isError, refetch, isFetching, invalidate } =
    usePimDataQuality();

  function handleRefresh() {
    invalidate();
    void refetch();
  }

  const generatedAgo = data?.generated_at ? timeAgo(data.generated_at) : null;

  return (
    <div className="space-y-6">
      {/* Sub-header con meta info + botón actualizar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {data ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold"
              style={{ background: MT.brandSoft, color: MT.brand }}
            >
              <BarChart2 className="size-3.5" />
              {data.total_skus} productos
            </span>
          ) : null}
          {generatedAgo ? (
            <span className="text-[12px]" style={{ color: MT.ink3 }}>
              Generado {generatedAgo}
            </span>
          ) : null}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isFetching}
          className="gap-1.5"
        >
          <RefreshCw
            className={`size-3.5 ${isFetching ? "animate-spin" : ""}`}
          />
          Actualizar
        </Button>
      </div>

      {/* Estados */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-4">
              <MtSkeleton height={18} className="mb-3 w-2/3" />
              <MtSkeleton height={36} className="mb-2 w-1/3" />
              <MtSkeleton height={6} className="mb-3 w-full" />
              <MtSkeleton height={12} className="mb-1 w-1/2" />
              <MtSkeleton height={12} className="w-2/5" />
            </Card>
          ))}
        </div>
      ) : isError ? (
        <MtError
          message="No se pudo cargar el reporte de calidad PIM."
          onRetry={handleRefresh}
        />
      ) : data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {GAP_CARDS.map((def) => (
            <GapCard key={def.key} def={def} gap={data.gaps[def.key]} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
