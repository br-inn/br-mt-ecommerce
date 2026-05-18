"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, Download, Sparkles, X } from "lucide-react";

import { MtButton, MtTh, MtTd, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { Paginator } from "@/app/(app)/catalogo/_components/paginator";
import {
  marketplaceListingsApi,
  type AmazonListingValidation,
  type AmazonValidationReport,
} from "@/lib/api/endpoints/marketplace-listings";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AmazonUaePage() {
  const router = useRouter();
  const [report, setReport] = React.useState<AmazonValidationReport | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [isExporting, setIsExporting] = React.useState(false);

  // Filter
  const [skuFilter, setSkuFilter] = React.useState("");

  // Pagination (client-side)
  const [page, setPage] = React.useState(0);
  const [pageSize, setPageSize] = React.useState(50);

  // Selection
  const [selectedSkus, setSelectedSkus] = React.useState<Set<string>>(new Set());

  // -------------------------------------------------------------------------
  // Load data
  // -------------------------------------------------------------------------
  const load = React.useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    else setIsLoading(true);
    try {
      const data = await marketplaceListingsApi.validateAmazon();
      setReport(data);
    } catch (err) {
      toast.error("No se pudo cargar el reporte de Amazon UAE", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------
  const allListings: AmazonListingValidation[] = report?.listings ?? [];

  const filtered = React.useMemo(() => {
    const q = skuFilter.trim().toLowerCase();
    if (!q) return allListings;
    return allListings.filter((l) => l.sku.toLowerCase().includes(q));
  }, [allListings, skuFilter]);

  const totalFiltered = filtered.length;
  const pageStart = page * pageSize;
  const pageItems = filtered.slice(pageStart, pageStart + pageSize);
  const hasNext = pageStart + pageSize < totalFiltered;
  const hasPrev = page > 0;

  // Reset page when filter or pageSize changes
  const handleSkuFilter = React.useCallback((v: string) => {
    setSkuFilter(v);
    setPage(0);
  }, []);

  const handlePageSize = React.useCallback((size: number) => {
    setPageSize(size);
    setPage(0);
  }, []);

  // -------------------------------------------------------------------------
  // Selection helpers
  // -------------------------------------------------------------------------
  const isAllFilteredSelected =
    filtered.length > 0 && filtered.every((l) => selectedSkus.has(l.sku));
  const isIndeterminate =
    filtered.some((l) => selectedSkus.has(l.sku)) && !isAllFilteredSelected;

  const toggleAll = React.useCallback(() => {
    setSelectedSkus((prev) => {
      const next = new Set(prev);
      if (isAllFilteredSelected) {
        filtered.forEach((l) => next.delete(l.sku));
      } else {
        filtered.forEach((l) => next.add(l.sku));
      }
      return next;
    });
  }, [filtered, isAllFilteredSelected]);

  const toggleRow = React.useCallback((sku: string) => {
    setSelectedSkus((prev) => {
      const next = new Set(prev);
      if (next.has(sku)) next.delete(sku);
      else next.add(sku);
      return next;
    });
  }, []);

  const selectReady = React.useCallback(() => {
    setSelectedSkus(new Set(filtered.filter((l) => l.is_ready).map((l) => l.sku)));
  }, [filtered]);

  const selectErrors = React.useCallback(() => {
    setSelectedSkus(new Set(filtered.filter((l) => l.errors.length > 0).map((l) => l.sku)));
  }, [filtered]);

  const selectAll = React.useCallback(() => {
    setSelectedSkus(new Set(filtered.map((l) => l.sku)));
  }, [filtered]);

  const clearSelection = React.useCallback(() => setSelectedSkus(new Set()), []);

  const readyCount = React.useMemo(
    () => filtered.filter((l) => l.is_ready).length,
    [filtered],
  );
  const errorCount = React.useMemo(
    () => filtered.filter((l) => l.errors.length > 0).length,
    [filtered],
  );

  // -------------------------------------------------------------------------
  // Row navigation
  // -------------------------------------------------------------------------
  const openDetail = React.useCallback(
    (item: AmazonListingValidation) => {
      try {
        sessionStorage.setItem("mt-amazon-nav", JSON.stringify(filtered.map((l) => l.sku)));
      } catch {
        // ignore
      }
      void router.push(`/canales/marketplace/amazon/${encodeURIComponent(item.sku)}`);
    },
    [router, filtered],
  );

  // -------------------------------------------------------------------------
  // Row actions
  // -------------------------------------------------------------------------
  const handleGenerate = React.useCallback(
    async (sku: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await marketplaceListingsApi.generateListing(sku, false);
        toast.success(`Listing generado para ${sku}`);
        void load(true);
      } catch (err) {
        toast.error(`Error al generar listing para ${sku}`, {
          description: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [load],
  );

  // -------------------------------------------------------------------------
  // Export
  // -------------------------------------------------------------------------
  const handleExport = React.useCallback(async () => {
    setIsExporting(true);
    try {
      const skus = selectedSkus.size > 0 ? [...selectedSkus] : undefined;
      await marketplaceListingsApi.downloadExport(skus);
    } catch (err) {
      toast.error("No se pudo exportar", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsExporting(false);
    }
  }, [selectedSkus]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-3"
        style={{ borderColor: MT.border, background: MT.surface }}
      >
        <div className="flex flex-col gap-0.5">
          <h1 className="text-[15px] font-semibold tracking-tight" style={{ color: MT.ink }}>
            Amazon UAE — Listings
          </h1>
          {report ? (
            <p className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
              {report.total_skus} SKUs &middot;{" "}
              <span style={{ color: MT.success }}>{report.ready_count} listos</span>
              {" · "}
              <span style={{ color: MT.warning }}>{report.draft_count} borradores</span>
              {" · "}
              <span style={{ color: MT.danger }}>{report.error_count} con errores</span>
            </p>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <input
            type="search"
            placeholder="Filtrar por SKU…"
            value={skuFilter}
            onChange={(e) => handleSkuFilter(e.target.value)}
            className="h-7 rounded-md border px-2.5 text-[12.5px] outline-none focus:ring-1"
            style={{
              borderColor: MT.border,
              background: MT.surface,
              color: MT.ink,
              minWidth: 180,
            }}
          />

          <MtButton
            tone="neutral"
            size="sm"
            icon={<RefreshCw className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />}
            onClick={() => void load(true)}
            disabled={isRefreshing}
          >
            Actualizar
          </MtButton>

          <MtButton
            tone={selectedSkus.size > 0 ? "primary" : "neutral"}
            size="sm"
            icon={<Download className={`size-3.5 ${isExporting ? "animate-pulse" : ""}`} />}
            onClick={() => void handleExport()}
            disabled={isExporting}
          >
            {isExporting
              ? "Exportando…"
              : selectedSkus.size > 0
                ? `Exportar selección (${selectedSkus.size})`
                : "Exportar CSV"}
          </MtButton>
        </div>
      </div>

      {/* ── Selection toolbar ── */}
      <div
        className="flex flex-wrap items-center gap-2 border-b px-6 py-2"
        style={{ borderColor: MT.border, background: MT.surface2 }}
      >
        <span className="text-[11.5px] font-medium" style={{ color: MT.ink3 }}>
          Selección rápida:
        </span>

        <button
          type="button"
          onClick={selectAll}
          className="rounded border px-2.5 py-0.5 text-[11.5px] transition-colors hover:bg-muted"
          style={{ borderColor: MT.border, color: MT.ink2 }}
        >
          Todos ({filtered.length})
        </button>

        <button
          type="button"
          onClick={selectReady}
          disabled={readyCount === 0}
          className="rounded border px-2.5 py-0.5 text-[11.5px] transition-colors hover:bg-muted disabled:opacity-40"
          style={{ borderColor: MT.successBorder, color: MT.success, background: MT.successSoft }}
        >
          Listos ({readyCount})
        </button>

        <button
          type="button"
          onClick={selectErrors}
          disabled={errorCount === 0}
          className="rounded border px-2.5 py-0.5 text-[11.5px] transition-colors hover:bg-muted disabled:opacity-40"
          style={{ borderColor: MT.dangerBorder, color: MT.danger, background: MT.dangerSoft }}
        >
          Con errores ({errorCount})
        </button>

        {selectedSkus.size > 0 ? (
          <>
            <span className="mx-1 opacity-20">|</span>
            <span className="text-[11.5px] font-semibold" style={{ color: MT.brand }}>
              {selectedSkus.size} seleccionados
            </span>
            <button
              type="button"
              onClick={clearSelection}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11.5px] transition-colors hover:opacity-70"
              style={{ color: MT.ink3 }}
            >
              <X className="size-3" />
              Limpiar
            </button>
          </>
        ) : null}
      </div>

      {/* ── Table ── */}
      <div className="mt-thin-scroll flex-1 overflow-auto" style={{ background: MT.bg }}>
        <div
          className="m-4 rounded-md border overflow-hidden"
          style={{ borderColor: MT.border }}
        >
          <table className="mt-data-table w-full border-separate border-spacing-0">
            <thead className="sticky top-0 z-10">
              <tr>
                {/* Checkbox select-all */}
                <MtTh style={{ width: 40, textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={isAllFilteredSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = isIndeterminate;
                    }}
                    onChange={toggleAll}
                    aria-label="Seleccionar todos"
                    className="cursor-pointer accent-[var(--color-brand,#2563eb)]"
                    onClick={(e) => e.stopPropagation()}
                  />
                </MtTh>
                <MtTh style={{ width: 140 }}>SKU</MtTh>
                <MtTh>Título</MtTh>
                <MtTh style={{ width: 140 }}>Estado</MtTh>
                <MtTh style={{ width: 120 }}>Alertas</MtTh>
                <MtTh style={{ width: 90 }}>Acciones</MtTh>
              </tr>
            </thead>
            <tbody>
              {/* Loading skeleton */}
              {isLoading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <tr key={`sk-${i}`}>
                      {Array.from({ length: 6 }).map((__, j) => (
                        <MtTd key={j}>
                          <div
                            className="animate-pulse rounded"
                            style={{
                              height: 14,
                              width: j === 0 ? 16 : j === 2 ? 220 : j === 1 ? 100 : 60,
                              background: MT.surface3,
                            }}
                          />
                        </MtTd>
                      ))}
                    </tr>
                  ))
                : null}

              {/* Empty state */}
              {!isLoading && pageItems.length === 0 ? (
                <tr>
                  <MtTd
                    colSpan={6}
                    className="text-center"
                    style={{ color: MT.ink3, paddingTop: 32, paddingBottom: 32 }}
                  >
                    No se encontraron productos.
                  </MtTd>
                </tr>
              ) : null}

              {/* Data rows */}
              {!isLoading
                ? pageItems.map((item, i) => {
                    const isEven = i % 2 === 0;
                    const isChecked = selectedSkus.has(item.sku);
                    return (
                      <tr
                        key={item.sku}
                        onClick={() => openDetail(item)}
                        style={{
                          background: isChecked
                            ? MT.brandSoft
                            : isEven
                              ? MT.surface
                              : MT.surface2,
                          boxShadow: isChecked ? `inset 3px 0 0 ${MT.brand}` : undefined,
                          cursor: "pointer",
                        }}
                      >
                        {/* Checkbox */}
                        <MtTd style={{ textAlign: "center" }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleRow(item.sku)}
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`Seleccionar ${item.sku}`}
                            className="cursor-pointer accent-[var(--color-brand,#2563eb)]"
                          />
                        </MtTd>

                        {/* SKU */}
                        <MtTd mono style={{ color: MT.brandDeep, fontWeight: 500 }}>
                          {item.sku}
                        </MtTd>

                        {/* Título — not in validation payload; see detail page */}
                        <MtTd style={{ color: MT.ink4 }}>
                          <span>—</span>
                        </MtTd>

                        {/* Estado */}
                        <MtTd>
                          {item.is_ready ? (
                            <Pill tone="success" dot>
                              Listo
                            </Pill>
                          ) : (
                            <Pill tone="danger" dot>
                              {item.errors.length} error
                              {item.errors.length !== 1 ? "es" : ""}
                            </Pill>
                          )}
                        </MtTd>

                        {/* Alertas */}
                        <MtTd>
                          {item.warnings.length > 0 ? (
                            <Pill tone="warning" dot>
                              {item.warnings.length} alerta
                              {item.warnings.length !== 1 ? "s" : ""}
                            </Pill>
                          ) : (
                            <span style={{ color: MT.ink4 }}>—</span>
                          )}
                        </MtTd>

                        {/* Acciones */}
                        <MtTd>
                          <button
                            type="button"
                            title="Generar con IA"
                            onClick={(e) => void handleGenerate(item.sku, e)}
                            className="flex size-6 items-center justify-center rounded hover:opacity-80"
                            style={{
                              background: MT.brandSoft,
                              color: MT.brand,
                              border: `1px solid ${MT.brandBorder}`,
                            }}
                          >
                            <Sparkles className="size-3.5" />
                          </button>
                        </MtTd>
                      </tr>
                    );
                  })
                : null}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Paginator ── */}
      <Paginator
        loaded={Math.min(pageStart + pageSize, totalFiltered)}
        total={totalFiltered}
        pageSize={pageSize}
        onPageSize={handlePageSize}
        hasNext={hasNext}
        onNext={() => setPage((p) => p + 1)}
        {...(hasPrev ? { onPrev: () => setPage((p) => p - 1) } : {})}
      />
    </div>
  );
}
