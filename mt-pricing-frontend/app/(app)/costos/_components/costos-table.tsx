"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import {
  MtButton,
  MtTd,
  MtTh,
  Pill,
  SectionCard,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  costState,
  type CostState,
} from "@/components/domain/costs/cost-state";
import type { Cost, CostFilters } from "@/lib/api/endpoints/costs";
import { useCosts } from "@/lib/hooks/costs/use-costs";
import { useCostosListFilters } from "./costos-filters";

const STATE_TONE: Record<CostState, "success" | "brand" | "ghost"> = {
  vigente: "success",
  programado: "brand",
  caducado: "ghost",
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

/**
 * Listado global de costes (tab "Costes" de `/costos`).
 *
 * Lista paginada (cursor infinito) de TODOS los costes, filtrable por
 * SKU / esquema / proveedor / fecha de vigencia / histórico vía
 * `useCostosListFilters` (estado en URL).
 */
export function CostosTable() {
  const t = useTranslations("costos");
  const { filters: urlFilters } = useCostosListFilters();

  const filters: CostFilters = React.useMemo(
    () => ({
      sku: urlFilters.sku,
      scheme: urlFilters.scheme,
      supplier: urlFilters.supplier,
      valid_on: urlFilters.valid_on,
      include_history: urlFilters.include_history,
    }),
    [
      urlFilters.sku,
      urlFilters.scheme,
      urlFilters.supplier,
      urlFilters.valid_on,
      urlFilters.include_history,
    ],
  );

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useCosts(filters);

  const items = React.useMemo<Cost[]>(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  if (isLoading) {
    return (
      <SectionCard>
        <div className="flex flex-col gap-2 p-4" data-testid="costos-loading">
          {Array.from({ length: 6 }).map((_, i) => (
            <MtSkeleton key={i} width="100%" height={28} />
          ))}
        </div>
      </SectionCard>
    );
  }

  if (isError) {
    return (
      <div data-testid="costos-error">
        <MtError message={t("errors.loadFailed")} onRetry={() => void refetch()} />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <SectionCard>
        <div data-testid="costos-empty">
          <MtEmpty title={t("empty.title")} hint={t("empty.description")} />
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard>
      <div className="space-y-3">
        <div className="overflow-x-auto" data-testid="costos-table-root">
          <table className="w-full border-separate border-spacing-0">
            <thead>
              <tr>
                <MtTh>{t("columns.sku")}</MtTh>
                <MtTh>{t("columns.scheme")}</MtTh>
                <MtTh>{t("columns.supplier")}</MtTh>
                <MtTh>{t("columns.validFrom")}</MtTh>
                <MtTh>{t("columns.validTo")}</MtTh>
                <MtTh className="text-right">{t("columns.landed")}</MtTh>
                <MtTh>{t("columns.state")}</MtTh>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => {
                const state = costState(c);
                const dimmed = state !== "vigente";
                return (
                  <tr
                    key={c.id}
                    style={{ opacity: dimmed ? 0.55 : 1 }}
                    data-testid={`costo-row-${c.id}`}
                  >
                    <MtTd mono className="font-medium">
                      <Link
                        href={`/catalogo/${encodeURIComponent(c.sku)}/costos`}
                        className="text-mt-brand hover:underline"
                      >
                        {c.sku}
                      </Link>
                    </MtTd>
                    <MtTd mono>{c.scheme_code}</MtTd>
                    <MtTd>{c.supplier_code ?? "—"}</MtTd>
                    <MtTd mono>{formatDate(c.valid_from)}</MtTd>
                    <MtTd mono>
                      {c.valid_to ? (
                        formatDate(c.valid_to)
                      ) : (
                        <span style={{ color: MT.ink3 }}>{t("open")}</span>
                      )}
                    </MtTd>
                    <MtTd mono className="text-right">
                      {formatNumber(c.scheme_landed_aed)}
                    </MtTd>
                    <MtTd>
                      <Pill tone={STATE_TONE[state]} dot>
                        {t(`states.${state}`)}
                      </Pill>
                    </MtTd>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div
          className="flex items-center justify-between px-4 py-2 text-[11.5px]"
          style={{ color: MT.ink3 }}
        >
          <span data-testid="costos-total-count">
            {t("totalCount", { count: items.length })}
          </span>
          {hasNextPage ? (
            <MtButton
              size="sm"
              tone="ghost"
              onClick={() => void fetchNextPage()}
              disabled={isFetchingNextPage}
              data-testid="costos-load-more"
            >
              {t("loadMore")}
            </MtButton>
          ) : null}
        </div>
      </div>
    </SectionCard>
  );
}

export default CostosTable;
