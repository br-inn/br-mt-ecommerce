/**
 * `/precios/aprobaciones` — Bandeja del Gerente (Wave 2 motor v5.1).
 *
 * Wired to `/api/v1/pricing/prices?status=pending_review` con bulk-approve y
 * approve/reject por fila. Usa `usePrices` + mutaciones de
 * `lib/hooks/pricing/use-pricing.ts`.
 */
"use client";

import * as React from "react";
import {
  Check,
  ChevronRight,
  Download,
  Filter,
  History,
  X,
} from "lucide-react";

import {
  FilterChip,
  Kbd,
  MtButton,
  MtTd,
  MtTh,
  Pill,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  useApprovePrice,
  useBulkApprovePrices,
  usePrices,
  useRejectPrice,
} from "@/lib/hooks/pricing/use-pricing";
import type { PriceRow, PriceStatus } from "@/lib/api/endpoints/pricing";

const FILTER_TABS: Array<{
  l: string;
  status: PriceStatus | "all";
  tone?: "brand" | "neutral";
}> = [
  { l: "Todo", status: "all" },
  { l: "Pendientes", status: "pending_review", tone: "brand" },
  { l: "Aprobadas", status: "approved" },
  { l: "Rechazadas", status: "rejected" },
];

function fmtAge(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} m`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.floor(h / 24);
  return `hace ${d} d`;
}

function fmtAED(amount: string): string {
  const n = parseFloat(amount);
  if (Number.isNaN(n)) return amount;
  return `${n.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} AED`;
}

export default function ApprovalsPage() {
  const [filter, setFilter] = React.useState<PriceStatus | "all">("pending_review");
  const [selected, setSelected] = React.useState<Record<string, boolean>>({});

  const filters = filter === "all" ? { include_total: true } : { status: filter, include_total: true };
  const { data, isLoading, isError, refetch, fetchNextPage, hasNextPage } =
    usePrices(filters);

  const items: PriceRow[] = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const pendingCount = items.length;
  const total = data?.pages[0]?.total ?? null;

  const approve = useApprovePrice();
  const reject = useRejectPrice();
  const bulk = useBulkApprovePrices();

  const selectedIds = Object.keys(selected).filter((id) => selected[id]);
  const allSelected = items.length > 0 && selectedIds.length === items.length;

  const toggleAll = () => {
    if (allSelected) {
      setSelected({});
    } else {
      const next: Record<string, boolean> = {};
      items.forEach((r) => {
        next[r.id] = true;
      });
      setSelected(next);
    }
  };

  const toggleOne = (id: string) =>
    setSelected((prev) => ({ ...prev, [id]: !prev[id] }));

  const onBulkApprove = () => {
    if (selectedIds.length === 0) return;
    bulk.mutate({ ids: selectedIds }, { onSuccess: () => setSelected({}) });
  };

  const onApprove = (id: string) => approve.mutate({ id });
  const onReject = (id: string) =>
    reject.mutate({ id, reason: "Rechazado desde bandeja del Gerente" });

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex items-center justify-between border-b bg-mt-surface px-6 py-3.5"
        style={{ borderColor: MT.border }}
      >
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs" style={{ color: MT.ink3 }}>
            <span>Operación</span>
            <ChevronRight className="size-3" style={{ color: MT.ink4 }} />
            <span className="font-semibold" style={{ color: MT.ink }}>
              Aprobaciones
            </span>
          </div>
          <h1
            className="m-0 text-[18px] font-semibold tracking-[-0.3px]"
            style={{ color: MT.ink }}
          >
            Bandeja del Gerente —{" "}
            <span style={{ color: MT.brand }}>
              {total !== null ? total : pendingCount}
            </span>{" "}
            propuestas{filter === "pending_review" ? " pendientes" : ""}
          </h1>
        </div>
        <div className="flex gap-1.5">
          <MtButton icon={<History className="size-3.5" />}>Historial</MtButton>
          <MtButton icon={<Download className="size-3.5" />}>Exportar audit</MtButton>
        </div>
      </div>

      {/* Filter row */}
      <div
        className="flex items-center gap-2 border-b bg-mt-surface px-6 py-2.5"
        style={{ borderColor: MT.border }}
      >
        {FILTER_TABS.map((t) => (
          <button
            key={t.l}
            type="button"
            onClick={() => setFilter(t.status)}
            className="cursor-pointer"
          >
            <FilterChip label={t.l} tone={t.tone} active={filter === t.status} />
          </button>
        ))}
        <span className="flex-1" />
        <MtButton size="sm" icon={<Filter className="size-3.5" />}>
          Más filtros
        </MtButton>
      </div>

      {/* Bulk actions */}
      {selectedIds.length > 0 ? (
        <div
          className="flex items-center gap-2.5 border-b px-6 py-2 text-[12.5px] font-medium"
          style={{ borderColor: MT.border, background: MT.brandSoft, color: MT.brand }}
        >
          <span className="mt-mono" style={{ color: MT.brandDeep }}>
            {selectedIds.length} seleccionado{selectedIds.length === 1 ? "" : "s"}
          </span>
          <span style={{ color: MT.ink4 }}>·</span>
          <MtButton
            size="sm"
            tone="primary"
            icon={<Check className="size-3.5" />}
            onClick={onBulkApprove}
            disabled={bulk.isPending}
          >
            {bulk.isPending ? "Aprobando…" : "Aprobar"}
          </MtButton>
          <MtButton size="sm" tone="ghost" onClick={() => setSelected({})}>
            Limpiar selección
          </MtButton>
          <span className="flex-1" />
          <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
            <Kbd>a</Kbd> aprobar · <Kbd>r</Kbd> rechazar · <Kbd>?</Kbd> atajos
          </span>
        </div>
      ) : null}

      {isError ? (
        <div className="px-6 py-3">
          <MtError
            message="No se pudieron cargar las propuestas."
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* Table */}
      <div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">
        <table className="mt-data-table w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 z-10">
            <tr>
              <MtTh style={{ width: 28 }}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  style={{ accentColor: MT.brand }}
                />
              </MtTh>
              <MtTh>SKU</MtTh>
              <MtTh>canal</MtTh>
              <MtTh>esquema</MtTh>
              <MtTh className="text-right">importe</MtTh>
              <MtTh className="text-right">margen</MtTh>
              <MtTh>estado</MtTh>
              <MtTh>autor</MtTh>
              <MtTh>edad</MtTh>
              <MtTh style={{ width: 90 }} className="text-right">
                acciones
              </MtTh>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    {Array.from({ length: 10 }).map((__, j) => (
                      <MtTd key={j}>
                        <MtSkeleton width={j === 1 ? 90 : 60} />
                      </MtTd>
                    ))}
                  </tr>
                ))
              : null}

            {!isLoading
              ? items.map((r) => {
                  const marginPct = parseFloat(r.margin_pct) * 100;
                  const isSel = !!selected[r.id];
                  return (
                    <tr
                      key={r.id}
                      style={{
                        background: isSel ? MT.brandSofter : MT.surface,
                        cursor: "pointer",
                      }}
                    >
                      <MtTd style={{ width: 28 }}>
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() => toggleOne(r.id)}
                          style={{ accentColor: MT.brand }}
                        />
                      </MtTd>
                      <MtTd mono className="font-medium" style={{ color: MT.brand }}>
                        {r.product_sku}
                      </MtTd>
                      <MtTd>
                        <Pill tone="ghost">{r.channel_id.slice(0, 8)}</Pill>
                      </MtTd>
                      <MtTd mono>{r.scheme_code}</MtTd>
                      <MtTd mono className="text-right font-medium" style={{ color: MT.ink }}>
                        {fmtAED(r.amount)}
                      </MtTd>
                      <MtTd mono className="text-right">
                        <span
                          style={{
                            color:
                              marginPct >= 30
                                ? MT.success
                                : marginPct >= 18
                                  ? MT.warning
                                  : MT.danger,
                          }}
                        >
                          {marginPct.toFixed(1)}%
                        </span>
                      </MtTd>
                      <MtTd>
                        <Pill
                          tone={
                            r.status === "approved" || r.status === "auto_approved"
                              ? "success"
                              : r.status === "rejected"
                                ? "danger"
                                : r.status === "pending_review"
                                  ? "brand"
                                  : "ghost"
                          }
                          dot
                        >
                          {r.status}
                        </Pill>
                      </MtTd>
                      <MtTd mono className="text-[11px]" style={{ color: MT.ink3 }}>
                        {r.proposed_by ? r.proposed_by.slice(0, 8) : "—"}
                      </MtTd>
                      <MtTd mono className="text-[11px]" style={{ color: MT.ink3 }}>
                        {fmtAge(r.created_at)}
                      </MtTd>
                      <MtTd>
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => onApprove(r.id)}
                            disabled={approve.isPending}
                            aria-label={`Aprobar ${r.product_sku}`}
                            className="grid size-[22px] place-items-center rounded-[4px] border"
                            style={{
                              background: MT.successSoft,
                              color: MT.success,
                              borderColor: MT.successBorder,
                            }}
                          >
                            <Check className="size-3" strokeWidth={2.5} />
                          </button>
                          <button
                            type="button"
                            onClick={() => onReject(r.id)}
                            disabled={reject.isPending}
                            aria-label={`Rechazar ${r.product_sku}`}
                            className="grid size-[22px] place-items-center rounded-[4px] border"
                            style={{
                              background: MT.dangerSoft,
                              color: MT.danger,
                              borderColor: MT.dangerBorder,
                            }}
                          >
                            <X className="size-3" strokeWidth={2.5} />
                          </button>
                        </div>
                      </MtTd>
                    </tr>
                  );
                })
              : null}
          </tbody>
        </table>

        {!isLoading && items.length === 0 && !isError ? (
          <MtEmpty
            title={filter === "pending_review" ? "Sin propuestas pendientes" : "Sin resultados"}
            hint="Las nuevas propuestas aparecerán aquí en cuanto Pricing Studio las envíe."
          />
        ) : null}
      </div>

      {/* Footer */}
      <div
        className="flex items-center justify-between border-t bg-mt-surface px-6 py-2 text-[11.5px]"
        style={{ borderColor: MT.border, color: MT.ink3 }}
      >
        <span>
          Mostrando {items.length}
          {total !== null ? ` de ${total}` : ""}
        </span>
        {hasNextPage ? (
          <MtButton size="sm" tone="ghost" onClick={() => void fetchNextPage()}>
            Cargar más
          </MtButton>
        ) : null}
      </div>
    </div>
  );
}
