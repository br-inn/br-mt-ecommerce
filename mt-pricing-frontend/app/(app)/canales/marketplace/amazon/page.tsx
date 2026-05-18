"use client";

import * as React from "react";
import { toast } from "sonner";
import { RefreshCw, Download, Sparkles } from "lucide-react";

import { MtButton, MtTh, MtTd, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { Paginator } from "@/app/(app)/catalogo/_components/paginator";
import {
  marketplaceListingsApi,
  type AmazonListingValidation,
  type AmazonValidationReport,
} from "@/lib/api/endpoints/marketplace-listings";
import { ListingDrawer } from "./_components/listing-drawer";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AmazonUaePage() {
  const [report, setReport] = React.useState<AmazonValidationReport | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  // Filter
  const [skuFilter, setSkuFilter] = React.useState("");

  // Pagination (client-side)
  const [page, setPage] = React.useState(0);
  const [pageSize, setPageSize] = React.useState(50);

  // Drawer
  const [drawerSku, setDrawerSku] = React.useState<string | null>(null);
  const [drawerValidation, setDrawerValidation] =
    React.useState<AmazonListingValidation | null>(null);

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
  // Row actions
  // -------------------------------------------------------------------------
  const openDrawer = React.useCallback((item: AmazonListingValidation) => {
    setDrawerSku(item.sku);
    setDrawerValidation(item);
  }, []);

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
  const handleExport = React.useCallback(() => {
    window.open(marketplaceListingsApi.getExportUrl(), "_blank");
  }, []);

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
          <h1
            className="text-[15px] font-semibold tracking-tight"
            style={{ color: MT.ink }}
          >
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
          {/* SKU filter */}
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
            tone="neutral"
            size="sm"
            icon={<Download className="size-3.5" />}
            onClick={handleExport}
          >
            Exportar CSV
          </MtButton>
        </div>
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
                      {Array.from({ length: 5 }).map((__, j) => (
                        <MtTd key={j}>
                          <div
                            className="animate-pulse rounded"
                            style={{
                              height: 14,
                              width: j === 1 ? 220 : j === 0 ? 100 : 60,
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
                    colSpan={5}
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
                    const isSelected = drawerSku === item.sku;
                    return (
                      <tr
                        key={item.sku}
                        onClick={() => openDrawer(item)}
                        style={{
                          background: isEven ? MT.surface : MT.surface2,
                          boxShadow: isSelected
                            ? `inset 3px 0 0 ${MT.brand}`
                            : undefined,
                          cursor: "pointer",
                        }}
                      >
                        {/* SKU — monospace, brand color, clickable */}
                        <MtTd mono style={{ color: MT.brandDeep, fontWeight: 500 }}>
                          {item.sku}
                        </MtTd>

                        {/* Título — not in validation payload; placeholder until drawer loads listing */}
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

      {/* ── Listing Drawer ── */}
      <ListingDrawer
        sku={drawerSku}
        validation={drawerValidation}
        onClose={() => setDrawerSku(null)}
        onGenerated={() => void load(true)}
      />
    </div>
  );
}
