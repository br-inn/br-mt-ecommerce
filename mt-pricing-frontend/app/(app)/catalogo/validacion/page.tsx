"use client";

import * as React from "react";
import {
  ArrowRight,
  ChevronLeft,
  Download,
  RefreshCcw,
  Trash2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

import {
  FilterChip,
  Kbd,
  MtButton,
} from "@/components/mt/primitives";
import { CandidateCard } from "./_components/candidate-card";
import { MtProductPanel } from "./_components/mt-product-panel";
import { SkuQueuePanel, type SkuQueueEntry } from "./_components/sku-queue-panel";
import { MtEmpty, MtError } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  useDiscardMatch,
  useMatches,
  useRefreshMatches,
  useValidateMatch,
} from "@/lib/hooks/matches/use-matches";
import { matchesApi } from "@/lib/api/endpoints/matches";
import { useQueryClient } from "@tanstack/react-query";
import type {
  MatchCandidate,
  MatchStatus,
} from "@/lib/api/endpoints/matches";

// ---------------------------------------------------------------------------
// SKU queue — unique SKUs with pending matches, ordered by first appearance,
// plus per-SKU candidate count and best score.
// ---------------------------------------------------------------------------

function useSkuQueue() {
  return useQuery<{ skus: string[]; stats: Map<string, { count: number; best: number }> }, Error>({
    queryKey: ["matches", "sku-queue"],
    queryFn: async () => {
      const res = await matchesApi.list({ status: "pending", limit: 200, include_total: false });
      const stats = new Map<string, { count: number; best: number }>();
      const skus: string[] = [];
      for (const c of res.items) {
        const prev = stats.get(c.product_sku);
        if (!prev) skus.push(c.product_sku);
        stats.set(c.product_sku, {
          count: (prev?.count ?? 0) + 1,
          best: Math.max(prev?.best ?? 0, c.score),
        });
      }
      return { skus, stats };
    },
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
// Main page
// ---------------------------------------------------------------------------

export default function ValidacionMatchesPage() {
  // A1 — Dynamic SKU queue
  const { data: queueData } = useSkuQueue();
  const queue = React.useMemo(() => queueData?.skus ?? [], [queueData]);
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

  const queryClient = useQueryClient();
  const refresh = useRefreshMatches();
  const validate = useValidateMatch();
  const discard = useDiscardMatch();
  const mutating = validate.isPending || discard.isPending;
  const scraping = refresh.isPending || refresh.isPolling;

  const [clearing, setClearing] = React.useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = React.useState(false);

  async function executeClearAll() {
    setClearing(true);
    try {
      const { deleted } = await matchesApi.clearAll();
      await queryClient.invalidateQueries({ queryKey: ["matches"] });
      toast.success(`${deleted} candidatos eliminados.`);
    } catch (err) {
      toast.error(`Error al limpiar: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setClearing(false);
    }
  }

  const queueEntries: SkuQueueEntry[] = React.useMemo(
    () =>
      queue.map((s) => {
        const st = queueData?.stats.get(s);
        return { sku: s, candidateCount: st?.count ?? 0, bestScore: st?.best ?? null };
      }),
    [queue, queueData],
  );

  const [queueCollapsed, setQueueCollapsed] = React.useState(false);

  // A2 — Prev / Next navigation
  const canPrev = clampedIndex > 0;
  const canNext = clampedIndex < queue.length - 1;

  const goNext = React.useCallback(() => {
    if (canNext) setSkuIndex((i) => i + 1);
  }, [canNext]);

  const goPrev = React.useCallback(() => {
    if (canPrev) setSkuIndex((i) => i - 1);
  }, [canPrev]);

  const goNextUnvalidated = React.useCallback(() => {
    for (let i = clampedIndex + 1; i < queue.length; i++) {
      const st = queueData?.stats.get(queue[i]!);
      if ((st?.count ?? 0) > 0) {
        setSkuIndex(i);
        return;
      }
    }
    if (canNext) setSkuIndex((x) => x + 1);
  }, [clampedIndex, queue, queueData, canNext]);

  // Keyboard nav: ← → for SKU navigation, V/X for validate/discard first pending
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
      const firstPending = items.find((c) => c.status === "pending");
      if (!firstPending || mutating) return;
      if (e.key === "v" || e.key === "V") validate.mutate(firstPending.id);
      if (e.key === "x" || e.key === "X") discard.mutate({ id: firstPending.id });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev, items, mutating, validate, discard]);

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
        <div className="flex items-center gap-2">
          <>
            <MtButton
              size="sm"
              icon={<Trash2 className="size-3" />}
              disabled={clearing}
              onClick={() => setConfirmClearOpen(true)}
            >
              {clearing ? "Limpiando…" : "Limpiar pruebas"}
            </MtButton>
            <ConfirmDialog
              open={confirmClearOpen}
              onOpenChange={setConfirmClearOpen}
              title="¿Borrar todos los candidatos de prueba?"
              description="Esta acción eliminará todos los candidatos de validación actuales. No se puede deshacer."
              confirmLabel="Borrar todo"
              destructive
              onConfirm={executeClearAll}
              busy={clearing}
            />
          </>
          <MtButton
            size="sm"
            icon={<RefreshCcw className={`size-3 ${scraping ? "animate-spin" : ""}`} />}
            onClick={() => queue.length > 0 && !scraping && refresh.mutate(sku)}
            disabled={scraping || queue.length === 0}
          >
            {refresh.isPending ? "Encolando…" : refresh.isPolling ? "Scrapendo…" : "Re-scrape"}
          </MtButton>
        </div>
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
      <div className="flex items-start gap-3 px-4 pb-20 pt-4">
        {/* SKU queue panel — colapsable */}
        <SkuQueuePanel
          entries={queueEntries}
          selectedIndex={clampedIndex}
          onSelect={setSkuIndex}
          collapsed={queueCollapsed}
          onToggle={() => setQueueCollapsed((v) => !v)}
        />

        {/* Left panel — ficha MT */}
        {queue.length > 0 ? (
          <MtProductPanel sku={sku} />
        ) : (
          <div
            className="mt-card-lift flex w-[280px] shrink-0 items-center justify-center rounded-lg border bg-mt-surface py-12"
            style={{ borderColor: MT.border, color: MT.ink4 }}
          >
            <span className="text-[12px]">Sin SKU seleccionado</span>
          </div>
        )}

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
          <span
            className="mt-mono cursor-pointer text-[14px] font-semibold hover:underline"
            style={{ color: MT.ink }}
            title={sku !== "—" ? `Copiar: ${sku}` : undefined}
            onClick={() => {
              if (sku !== "—") void navigator.clipboard.writeText(sku);
            }}
          >
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
          onClick={goNextUnvalidated}
          disabled={!canNext}
        >
          Siguiente sin validar
        </MtButton>
      </div>
    </div>
  );
}
