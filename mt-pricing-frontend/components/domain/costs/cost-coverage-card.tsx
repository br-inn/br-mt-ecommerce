"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { KpiCard } from "@/components/mt/primitives";
import { type SchemeCoverage } from "@/lib/api/endpoints/cost-dashboard";

interface Props {
  coverage: SchemeCoverage;
  totalProducts: number;
}

/**
 * Cost coverage KPI por scheme — calcula `covered` = total - missing.
 * Si missing == 0 → tone success; si missing > 50% → danger; else warning.
 */
export function CostCoverageCard({ coverage, totalProducts }: Props) {
  const t = useTranslations("costsDashboard");
  const covered = Math.max(0, totalProducts - coverage.missingCount);
  const pct =
    totalProducts > 0 ? Math.round((covered / totalProducts) * 100) : 0;

  const tone: "success" | "warning" | "danger" =
    coverage.missingCount === 0
      ? "success"
      : coverage.missingCount > totalProducts / 2
        ? "danger"
        : "warning";

  return (
    <KpiCard
      label={t("schemeKpiLabel", { scheme: coverage.scheme })}
      value={`${pct}%`}
      sub={t("coveredOfTotal", { covered, total: totalProducts })}
      tone={tone}
      badge={
        coverage.missingCount > 0
          ? t("missingCount", { count: coverage.missingCount })
          : t("complete")
      }
    />
  );
}

/**
 * Tabla pequeña con SKUs faltantes por scheme — links a `/catalogo/[sku]/costos`.
 * Usado debajo del overview por scheme expandible.
 */
export function MissingSkusTable({ coverage }: { coverage: SchemeCoverage }) {
  const t = useTranslations("costsDashboard");

  if (coverage.missing.length === 0) {
    return (
      <p className="px-4 py-3 text-xs text-muted-foreground">
        {t("noMissing")}
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full text-xs">
        <thead className="bg-muted/30">
          <tr>
            <th className="px-3 py-2 text-left font-medium">SKU</th>
            <th className="px-3 py-2 text-left font-medium">{t("name")}</th>
            <th className="px-3 py-2 text-right font-medium">
              {t("actions")}
            </th>
          </tr>
        </thead>
        <tbody>
          {coverage.missing.slice(0, 50).map((row) => (
            <tr key={row.sku} className="border-t">
              <td className="px-3 py-2 font-mono">{row.sku}</td>
              <td className="px-3 py-2 text-muted-foreground">
                {row.name ?? "—"}
              </td>
              <td className="px-3 py-2 text-right">
                <Link
                  href={`/catalogo/${encodeURIComponent(row.sku)}/costos`}
                  className="text-primary hover:underline"
                >
                  {t("addCost")}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {coverage.missing.length > 50 ? (
        <p className="border-t px-3 py-2 text-[11px] text-muted-foreground">
          {t("missingCapped", {
            shown: 50,
            total: coverage.missing.length,
          })}
        </p>
      ) : null}
    </div>
  );
}
