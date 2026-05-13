"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  Download,
  ExternalLink,
  FileText,
  History,
  Image as ImageIcon,
  RefreshCcw,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import {
  FilterChip,
  Kbd,
  MtButton,
  Pill,
  ScorePill,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CompetitorTag({ kind, country }: { kind: MatchCandidate["kind"]; country?: string }) {
  const map = {
    peer: { bg: MT.brandSoft, fg: MT.brand, bd: MT.brandBorder, label: "Peer fabricante" },
    drop: { bg: MT.surface3, fg: MT.ink3, bd: MT.border, label: "Distribuidor" },
    unknown: { bg: MT.surface3, fg: MT.ink4, bd: MT.border, label: "Sin clasificar" },
  } as const;
  const t = map[kind];
  return (
    <span
      className="inline-flex h-[17px] items-center gap-1 whitespace-nowrap rounded-[3px] border px-1.5 text-[10px] font-medium leading-none"
      style={{ background: t.bg, color: t.fg, borderColor: t.bd }}
    >
      {t.label}
      {country ? ` · ${country}` : ""}
    </span>
  );
}

function SpecLine({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-1 text-[11px] leading-[1.4]">
      <span className="min-w-[56px]" style={{ color: MT.ink4 }}>
        {k}
      </span>
      <span
        className={/[0-9]/.test(v) ? "mt-mono font-medium" : "font-medium"}
        style={{ color: MT.ink2 }}
      >
        {v}
      </span>
    </div>
  );
}

function CandidateRow({
  c,
  onValidate,
  onDiscard,
  pending,
}: {
  c: MatchCandidate;
  onValidate: () => void;
  onDiscard: () => void;
  pending: boolean;
}) {
  const isVal = c.status === "validated";
  const isDis = c.status === "discarded";
  const bg = isVal ? "#F4FBF6" : isDis ? "#FBF5F4" : MT.surface;
  const leftBar = isVal ? MT.success : isDis ? MT.danger : "transparent";
  const specs = c.specs_jsonb as Record<string, string | null | undefined>;
  const priceNum = c.price_aed === null ? null : Number(c.price_aed);

  return (
    <tr style={{ background: bg, borderBottom: `1px solid ${MT.border}`, position: "relative" }}>
      <td className="relative w-[200px] px-3.5 py-3 align-top">
        <span className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ background: leftBar }} />
        <div className="mb-1 text-[12.5px] font-semibold" style={{ color: MT.ink }}>
          {c.brand ?? "—"}
        </div>
        <div className="mb-1.5">
          <CompetitorTag kind={c.kind} />
        </div>
        <div className="mt-mono text-[10px]" style={{ color: MT.ink4 }}>
          ASIN · {c.external_id}
        </div>
        <div className="mt-1.5 text-[11px] leading-[1.3]" style={{ color: MT.ink3 }}>
          {c.title}
        </div>
      </td>
      <td className="w-16 px-2 py-3 align-top">
        <div
          className="grid size-14 place-items-center rounded-[4px] border"
          style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink4 }}
        >
          <ImageIcon className="size-5" strokeWidth={1.4} />
        </div>
      </td>
      <td className="px-3.5 py-3 align-top">
        <div className="flex flex-col gap-[3px]">
          <SpecLine k="Material" v={String(specs?.material ?? "—")} />
          <SpecLine k="Tipo" v={String(specs?.valve_type ?? specs?.type ?? "—")} />
          <SpecLine k="Rosca" v={String(specs?.thread ?? "—")} />
          <SpecLine k="PN" v={String(specs?.pn ?? "—")} />
          <SpecLine k="Norma" v={String(specs?.norma ?? "—")} />
        </div>
      </td>
      <td className="w-[130px] px-3 py-3 align-top">
        <span className="text-[11px]" style={{ color: MT.ink2 }}>
          {c.delivery_text ?? "—"}
        </span>
      </td>
      <td className="w-[120px] px-3.5 py-3 text-right align-top">
        <div className="mt-mono text-[15px] font-bold tracking-[-0.2px]" style={{ color: MT.ink }}>
          {fmtAED(priceNum)}
        </div>
        <div className="mt-2">
          <ScorePill score={c.score} />
        </div>
      </td>
      <td className="w-[170px] px-3.5 py-3 align-top">
        <div className="flex flex-col gap-1.5">
          {isVal ? (
            <span
              className="inline-flex h-[26px] items-center justify-center gap-1.5 rounded-[4px] border px-2.5 text-[11.5px] font-semibold"
              style={{ color: MT.success, background: MT.successSoft, borderColor: MT.successBorder }}
            >
              <Check className="size-3" strokeWidth={2.5} /> Validado
            </span>
          ) : isDis ? (
            <span
              className="inline-flex h-[26px] items-center justify-center gap-1.5 rounded-[4px] border px-2.5 text-[11.5px] font-semibold"
              style={{ color: MT.danger, background: MT.dangerSoft, borderColor: MT.dangerBorder }}
            >
              <X className="size-3" strokeWidth={2.5} /> Descartado
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={onValidate}
                disabled={pending}
                className="inline-flex h-[26px] cursor-pointer items-center justify-center gap-1.5 rounded-[4px] border px-2.5 text-[11.5px] font-semibold text-white disabled:opacity-50"
                style={{ background: MT.brand, borderColor: MT.brand }}
              >
                <Check className="size-3" strokeWidth={2.5} /> Validar match
              </button>
              <button
                type="button"
                onClick={onDiscard}
                disabled={pending}
                className="inline-flex h-6 cursor-pointer items-center justify-center gap-1.5 rounded-[4px] border px-2.5 text-[11px] font-medium disabled:opacity-50"
                style={{ color: MT.ink3, borderColor: MT.border }}
              >
                Descartar
              </button>
            </>
          )}
          {/* A6 — Amazon UAE link via ASIN */}
          <a
            href={`https://www.amazon.ae/dp/${c.external_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-mono inline-flex h-[22px] items-center justify-center gap-1 text-[10.5px] hover:underline"
            style={{ color: MT.ink3 }}
          >
            <ExternalLink className="size-3" /> Amazon UAE
          </a>
        </div>
      </td>
    </tr>
  );
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
            className="flex items-center justify-between border-b px-4 py-3"
            style={{ background: MT.surface2, borderColor: MT.border }}
          >
            <div>
              <div className="text-[13.5px] font-semibold" style={{ color: MT.ink }}>
                Candidatos · {items.length} encontrados
              </div>
            </div>
          </div>
          <table className="w-full table-auto border-collapse">
            <thead>
              <tr className="border-b" style={{ background: MT.surface2, borderColor: MT.border }}>
                {["Marca · ASIN", "Foto", "Specs (PDP)", "Plazo", "Precio · Score", "Decisión"].map(
                  (h, i) => (
                    <th
                      key={h}
                      className="mt-mono border-b px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.6px]"
                      style={{
                        color: MT.ink4,
                        borderColor: MT.border,
                        textAlign: i === 4 ? "right" : "left",
                      }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={`sk-${i}`}>
                      {Array.from({ length: 6 }).map((__, j) => (
                        <td key={j} className="px-3.5 py-3">
                          <MtSkeleton width="100%" height={48} />
                        </td>
                      ))}
                    </tr>
                  ))
                : null}
              {!isLoading
                ? items.map((c) => (
                    <CandidateRow
                      key={c.id}
                      c={c}
                      pending={mutating}
                      onValidate={() => validate.mutate(c.id)}
                      onDiscard={() => discard.mutate({ id: c.id })}
                    />
                  ))
                : null}
            </tbody>
          </table>
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
