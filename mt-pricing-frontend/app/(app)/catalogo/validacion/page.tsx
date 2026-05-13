"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  ChevronLeft,
  Download,
  FileText,
  History,
  RefreshCcw,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import {
  FilterChip,
  Kbd,
  MtButton,
  Pill,
} from "@/components/mt/primitives";
import { CandidateCard } from "./_components/candidate-card";
import { MtEmpty, MtError } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  useDiscardMatch,
  useMatches,
  useRefreshMatches,
  useValidateMatch,
} from "@/lib/hooks/matches/use-matches";
import { useProduct } from "@/lib/hooks/products/use-product";
import { matchesApi } from "@/lib/api/endpoints/matches";
import type {
  MatchCandidate,
  MatchStatus,
} from "@/lib/api/endpoints/matches";

// ---------------------------------------------------------------------------
// SKU queue — unique SKUs with pending matches, ordered by first appearance.
// ---------------------------------------------------------------------------

function usePendingSkuQueue() {
  return useQuery<string[], Error>({
    queryKey: ["matches", "pending-sku-queue"],
    queryFn: async () => {
      const res = await matchesApi.list({ status: "pending", limit: 200, include_total: false });
      const seen = new Set<string>();
      const skus: string[] = [];
      for (const c of res.items) {
        if (!seen.has(c.product_sku)) {
          seen.add(c.product_sku);
          skus.push(c.product_sku);
        }
      }
      return skus;
    },
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const fmtAED = (n: number | null) =>
  n == null ? "—" : `AED ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n)}`;

function exportToCsv(items: MatchCandidate[], sku: string) {
  const headers: Array<keyof MatchCandidate> = [
    "brand",
    "external_id",
    "title",
    "kind",
    "price_aed",
    "score",
    "status",
    "delivery_text",
  ];
  const rows = items.map((c) =>
    headers.map((h) => {
      const v = c[h];
      return `"${String(v ?? "").replace(/"/g, '""')}"`;
    }).join(","),
  );
  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `matches-${sku}-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}


const FILTER_TABS: Array<{ l: string; status: MatchStatus | "all" }> = [
  { l: "Todas", status: "all" },
  { l: "Pendientes", status: "pending" },
  { l: "Validadas", status: "validated" },
  { l: "Descartadas", status: "discarded" },
];

// ---------------------------------------------------------------------------
// A5 — Product pills derived from data_quality and series_detail
// ---------------------------------------------------------------------------

function ProductPills({ sku }: { sku: string }) {
  const { data: product } = useProduct(sku);

  const tierLabel = product?.series_detail?.tier_id
    ? `Tier ${product.series_detail.tier_id.slice(0, 4)}`
    : "G1 propuesto";

  const qualityLabel =
    product?.data_quality === "complete"
      ? "Calidad completa"
      : product?.data_quality === "blocked"
        ? "Bloqueado CG"
        : "Pendiente CG";

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      <Pill tone="brand">{tierLabel}</Pill>
      <Pill>{qualityLabel}</Pill>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ValidacionMatchesPage() {
  // A1 — Dynamic SKU queue
  const { data: queue = [] } = usePendingSkuQueue();
  const [skuIndex, setSkuIndex] = React.useState(0);

  // When queue loads, keep index in bounds
  const clampedIndex = queue.length > 0 ? Math.min(skuIndex, queue.length - 1) : 0;
  const sku = queue[clampedIndex] ?? "—";

  const [statusFilter, setStatusFilter] = React.useState<MatchStatus | "all">("pending");

  const filters: import("@/lib/api/endpoints/matches").MatchFilters = {
    include_total: true,
    ...(queue.length > 0 ? { sku } : {}),
    ...(statusFilter !== "all" ? { status: statusFilter } : {}),
  };
  const { data, isLoading, isError, refetch } = useMatches(filters);

  const items: MatchCandidate[] = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const total = data?.pages[0]?.total ?? null;

  const refresh = useRefreshMatches();
  const validate = useValidateMatch();
  const discard = useDiscardMatch();
  const mutating = validate.isPending || discard.isPending;

  // A2 — Prev / Next navigation
  const canPrev = clampedIndex > 0;
  const canNext = clampedIndex < queue.length - 1;

  const goNext = React.useCallback(() => {
    if (canNext) setSkuIndex((i) => i + 1);
  }, [canNext]);

  const goPrev = React.useCallback(() => {
    if (canPrev) setSkuIndex((i) => i - 1);
  }, [canPrev]);

  // Keyboard nav: ← → for SKU navigation, V/X for validate/discard first pending
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev]);

  const tabCounts: Record<string, number | undefined> = {
    all: statusFilter === "all" ? (total ?? undefined) : undefined,
    pending: statusFilter === "pending" ? (total ?? undefined) : undefined,
    validated: statusFilter === "validated" ? (total ?? undefined) : undefined,
    discarded: statusFilter === "discarded" ? (total ?? undefined) : undefined,
  };

  return (
    <div className="h-full overflow-auto">
      {/* Workflow header — barra delgada */}
      <div
        className="flex h-9 items-center justify-between gap-4 border-b px-5"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <div className="flex items-center gap-2">
          <span className="mt-mono text-[10.5px] uppercase tracking-[1px]" style={{ color: MT.ink4 }}>
            Validación
          </span>
          <span style={{ color: MT.border }}>›</span>
          <span className="mt-mono text-[12px] font-semibold" style={{ color: MT.ink }}>
            {sku === "—" ? "—" : sku}
          </span>
          {queue.length > 0 && (
            <span
              className="ml-1 inline-flex h-5 items-center rounded-[4px] border px-1.5 text-[10.5px] font-medium"
              style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink3 }}
            >
              {queue.length - clampedIndex} pendientes
            </span>
          )}
        </div>
        <MtButton
          size="sm"
          icon={<RefreshCcw className="size-3" />}
          onClick={() => queue.length > 0 && refresh.mutate(sku)}
          disabled={refresh.isPending || queue.length === 0}
        >
          {refresh.isPending ? "Re-scraping…" : "Re-scrape"}
        </MtButton>
      </div>

      {/* Toolbar */}
      <div
        className="flex items-center justify-between gap-4 border-b bg-mt-surface px-6 py-2.5"
        style={{ borderColor: MT.border }}
      >
        <div className="flex items-center gap-1.5">
          <span
            className="mt-mono mr-1 text-[10.5px] uppercase tracking-[0.6px]"
            style={{ color: MT.ink4 }}
          >
            Filtro
          </span>
          {FILTER_TABS.map((t) => (
            <button
              key={t.l}
              type="button"
              onClick={() => setStatusFilter(t.status)}
              className="cursor-pointer"
            >
              <FilterChip
                label={t.l}
                count={tabCounts[t.status]}
                active={statusFilter === t.status}
              />
            </button>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
            <span className="font-semibold" style={{ color: MT.ink }}>
              {items.length}
            </span>{" "}
            {total !== null ? `/ ${total} en total` : "candidatos"}
          </span>
          {/* A7 — CSV export */}
          <MtButton
            size="sm"
            icon={<Download className="size-3.5" />}
            onClick={() => exportToCsv(items, sku)}
            disabled={items.length === 0}
          >
            Exportar
          </MtButton>
        </div>
      </div>

      {isError ? (
        <div className="px-6 py-3">
          <MtError
            message="No se pudieron cargar los candidatos."
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* Body */}
      <div className="flex items-start gap-[18px] px-6 pb-20 pt-5">
        {/* Left panel — SKU info */}
        <div
          className="mt-card-lift flex w-[300px] shrink-0 flex-col self-start overflow-hidden rounded-lg border bg-mt-surface"
          style={{ borderColor: MT.border }}
        >
          <div className="flex flex-col gap-3 p-3.5">
            <div>
              <div
                className="mt-mono mb-1 text-[11px] tracking-[0.4px]"
                style={{ color: MT.ink4 }}
              >
                REF.
              </div>
              <div className="mt-mono text-[14px] font-semibold leading-[1.3]" style={{ color: MT.ink }}>
                {sku}
              </div>
              {/* A5 — Dynamic product pills */}
              {queue.length > 0 ? (
                <ProductPills sku={sku} />
              ) : (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Pill tone="brand">G1 propuesto</Pill>
                  <Pill>Pendiente CG</Pill>
                </div>
              )}
            </div>
            <div
              className="rounded-[5px] border px-2.5 py-2 text-[11px]"
              style={{ background: MT.surface2, borderColor: MT.border, color: MT.ink2 }}
            >
              Ficha técnica completa disponible en{" "}
              <a
                href={`/catalogo/${sku}`}
                className="cursor-pointer underline"
                style={{ color: MT.brand }}
              >
                /catalogo/{sku}
              </a>
            </div>
            {/* A4 — Abrir ficha + Histórico with real hrefs */}
            <div className="flex gap-1.5 pt-1">
              <MtButton size="sm" className="flex-1 justify-center" asChild>
                <Link href={`/catalogo/${sku}`}>
                  <FileText className="size-3.5" />
                  Abrir ficha
                </Link>
              </MtButton>
              <MtButton size="sm" className="flex-1 justify-center" asChild>
                <Link href={`/catalogo/${sku}/audit`}>
                  <History className="size-3.5" />
                  Histórico
                </Link>
              </MtButton>
            </div>
          </div>
        </div>

        {/* Candidates */}
        <div
          className="mt-card-lift min-w-0 flex-1 overflow-hidden rounded-lg border bg-mt-surface"
          style={{ borderColor: MT.border }}
        >
          <div
            className="flex items-center justify-between border-b px-4 py-2.5"
            style={{ background: MT.surface2, borderColor: MT.border }}
          >
            <span className="text-[13px] font-semibold" style={{ color: MT.ink }}>
              Candidatos Amazon UAE
            </span>
            <span className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
              {items.length} resultado{items.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex flex-col gap-2 p-3">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={`sk-${i}`}
                    className="h-[112px] animate-pulse rounded-lg"
                    style={{ background: MT.surface3 }}
                  />
                ))
              : items.map((c) => (
                  <CandidateCard
                    key={c.id}
                    candidate={c}
                    pending={mutating}
                    onValidate={() => validate.mutate(c.id)}
                    onDiscard={() => discard.mutate({ id: c.id })}
                  />
                ))}
          </div>
          {!isLoading && items.length === 0 && !isError ? (
            <MtEmpty
              title="Sin candidatos"
              hint="Pulsa Re-scrape para encolar un nuevo barrido del scraper."
            />
          ) : null}
        </div>
      </div>

      {/* Bottom nav — A2: prev/next + position indicator */}
      <div
        className="sticky bottom-0 flex items-center justify-between gap-4 border-t bg-mt-surface px-6 py-2.5"
        style={{
          borderColor: MT.border,
          boxShadow: "0 -1px 0 rgba(15,23,42,.02), 0 -8px 16px -8px rgba(15,23,42,.04)",
        }}
      >
        <MtButton
          size="sm"
          icon={<ChevronLeft className="size-3.5" />}
          onClick={goPrev}
          disabled={!canPrev}
        >
          Anterior
        </MtButton>

        <div className="flex items-center gap-3.5">
          {/* Position indicator */}
          {queue.length > 0 && (
            <span className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
              SKU{" "}
              <span className="font-semibold" style={{ color: MT.ink }}>
                {clampedIndex + 1}
              </span>{" "}
              de{" "}
              <span className="font-semibold" style={{ color: MT.ink }}>
                {queue.length}
              </span>{" "}
              pendientes
            </span>
          )}
          <span className="mt-mono text-[11px] uppercase tracking-[0.6px]" style={{ color: MT.ink4 }}>
            SKU
          </span>
          <span className="mt-mono text-[14px] font-semibold" style={{ color: MT.ink }}>
            {sku}
          </span>
          <span className="h-[18px] w-px" style={{ background: MT.border }} />
          <span className="flex items-center gap-1.5 text-[11px]" style={{ color: MT.ink3 }}>
            <Kbd>←</Kbd> <Kbd>→</Kbd> navegar
            <span className="mx-1.5" style={{ color: MT.ink4 }}>·</span>
            <Kbd>V</Kbd> validar
            <span className="mx-1.5" style={{ color: MT.ink4 }}>·</span>
            <Kbd>X</Kbd> descartar
          </span>
        </div>

        <MtButton
          size="sm"
          tone="primary"
          icon={<ArrowRight className="size-3.5" />}
          onClick={goNext}
          disabled={!canNext}
        >
          Siguiente sin validar
        </MtButton>
      </div>
    </div>
  );
}
