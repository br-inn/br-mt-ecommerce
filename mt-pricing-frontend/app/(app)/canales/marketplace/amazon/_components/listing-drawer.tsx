"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  Loader2,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Sparkles,
  X,
} from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import {
  marketplaceListingsApi,
  type AmazonListingValidation,
  type MarketplaceListingRead,
} from "@/lib/api/endpoints/marketplace-listings";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ListingDrawerProps {
  /** null = drawer closed */
  sku: string | null;
  validation: AmazonListingValidation | null;
  onClose: () => void;
  /** Called after successful AI generation so the parent can refresh the table */
  onGenerated: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ListingDrawer({
  sku,
  validation,
  onClose,
  onGenerated,
}: ListingDrawerProps) {
  const open = sku !== null;

  const [listing, setListing] = React.useState<MarketplaceListingRead | null>(null);
  const [listingLoading, setListingLoading] = React.useState(false);
  const [listingError, setListingError] = React.useState<string | null>(null);

  const [generating, setGenerating] = React.useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = React.useState(false);

  // Fetch listing content when drawer opens
  React.useEffect(() => {
    if (!sku) {
      setListing(null);
      setListingError(null);
      setConfirmOverwrite(false);
      return;
    }

    setListingLoading(true);
    setListingError(null);
    setListing(null);

    marketplaceListingsApi
      .getListing(sku)
      .then((data) => {
        setListing(data);
      })
      .catch(() => {
        // 404 is expected when no listing exists yet
        setListingError(null);
      })
      .finally(() => {
        setListingLoading(false);
      });
  }, [sku]);

  // -------------------------------------------------------------------------
  // Generate action
  // -------------------------------------------------------------------------
  const handleGenerate = React.useCallback(async () => {
    if (!sku) return;

    const hasContent =
      listing &&
      (listing.listing_title ||
        listing.listing_description ||
        listing.bullet_points.length > 0);

    if (hasContent && !confirmOverwrite) {
      setConfirmOverwrite(true);
      return;
    }

    setGenerating(true);
    setConfirmOverwrite(false);
    try {
      const result = await marketplaceListingsApi.generateListing(sku, hasContent ? true : false);
      setListing(result);
      toast.success(`Listing generado para ${sku}`);
      onGenerated();
    } catch (err) {
      toast.error(`Error al generar listing para ${sku}`, {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setGenerating(false);
    }
  }, [sku, listing, confirmOverwrite, onGenerated]);

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------
  const keywords: string[] = React.useMemo(() => {
    if (!listing?.search_keywords) return [];
    return listing.search_keywords
      .split(/[,\n]/)
      .map((k) => k.trim())
      .filter(Boolean);
  }, [listing?.search_keywords]);

  const hasErrors = (validation?.errors.length ?? 0) > 0;
  const hasWarnings = (validation?.warnings.length ?? 0) > 0;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent
        side="right"
        className="flex w-full max-w-lg flex-col overflow-hidden p-0"
        style={{ borderLeft: `1px solid ${MT.border}` }}
      >
        {/* ── Sheet Header ── */}
        <SheetHeader
          className="shrink-0 border-b px-5 py-4"
          style={{ borderColor: MT.border, background: MT.surface2 }}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <SheetTitle
                className="mt-mono truncate text-[13px] font-semibold"
                style={{ color: MT.brandDeep }}
              >
                {sku ?? "—"}
              </SheetTitle>
              <Pill tone="brand">Amazon UAE</Pill>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex size-6 shrink-0 items-center justify-center rounded hover:opacity-70"
              style={{ color: MT.ink3 }}
              aria-label="Cerrar"
            >
              <X className="size-4" />
            </button>
          </div>
        </SheetHeader>

        {/* ── Body (scrollable) ── */}
        <div className="mt-thin-scroll flex-1 overflow-y-auto px-5 py-4 space-y-5">

          {/* ── Validation status ── */}
          {validation ? (
            <section className="space-y-2">
              {validation.is_ready ? (
                <div
                  className="flex items-center gap-2 rounded-md border px-3 py-2.5 text-[12.5px]"
                  style={{
                    background: MT.successSoft,
                    borderColor: MT.successBorder,
                    color: MT.success,
                  }}
                >
                  <CheckCircle className="size-4 shrink-0" />
                  <span className="font-medium">Listo para exportar</span>
                </div>
              ) : null}

              {hasErrors ? (
                <div
                  className="rounded-md border px-3 py-2.5 text-[12.5px] space-y-1.5"
                  style={{
                    background: MT.dangerSoft,
                    borderColor: MT.dangerBorder,
                    color: MT.danger,
                  }}
                >
                  <div className="flex items-center gap-2 font-medium">
                    <AlertCircle className="size-4 shrink-0" />
                    {validation.errors.length} error
                    {validation.errors.length !== 1 ? "es" : ""}
                  </div>
                  <ul className="ml-6 list-disc space-y-0.5" style={{ color: MT.danger }}>
                    {validation.errors.map((e, i) => (
                      <li key={i} className="text-[11.5px]">
                        <span className="font-medium">{e.field}:</span> {e.message}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {hasWarnings ? (
                <div
                  className="rounded-md border px-3 py-2.5 text-[12.5px] space-y-1.5"
                  style={{
                    background: MT.warningSoft,
                    borderColor: MT.warningBorder,
                    color: MT.warning,
                  }}
                >
                  <div className="flex items-center gap-2 font-medium">
                    <AlertTriangle className="size-4 shrink-0" />
                    {validation.warnings.length} alerta
                    {validation.warnings.length !== 1 ? "s" : ""}
                  </div>
                  <ul className="ml-6 list-disc space-y-0.5">
                    {validation.warnings.map((w, i) => (
                      <li key={i} className="text-[11.5px]">
                        <span className="font-medium">{w.field}:</span> {w.message}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          ) : null}

          {/* ── Listing content ── */}
          <section className="space-y-4">
            <h2
              className="mt-mono text-[10.5px] font-medium uppercase tracking-[0.5px]"
              style={{ color: MT.ink3 }}
            >
              Contenido del Listing
            </h2>

            {listingLoading ? (
              <div className="flex items-center gap-2 text-[12.5px]" style={{ color: MT.ink3 }}>
                <Loader2 className="size-4 animate-spin" />
                <span>Cargando listing…</span>
              </div>
            ) : listingError ? (
              <p className="text-[12.5px]" style={{ color: MT.danger }}>
                {listingError}
              </p>
            ) : listing ? (
              <div className="space-y-4">
                {/* Título */}
                <div className="space-y-1">
                  <label
                    className="mt-mono text-[10.5px] font-medium uppercase tracking-[0.5px]"
                    style={{ color: MT.ink4 }}
                  >
                    Título
                  </label>
                  <p className="text-[13px]" style={{ color: listing.listing_title ? MT.ink : MT.ink4 }}>
                    {listing.listing_title ?? "Sin título"}
                  </p>
                </div>

                {/* Descripción */}
                {listing.listing_description ? (
                  <div className="space-y-1">
                    <label
                      className="mt-mono text-[10.5px] font-medium uppercase tracking-[0.5px]"
                      style={{ color: MT.ink4 }}
                    >
                      Descripción
                    </label>
                    <div
                      className="rounded-md border px-3 py-2.5 text-[12.5px] leading-relaxed whitespace-pre-wrap"
                      style={{
                        borderColor: MT.border,
                        background: MT.surface2,
                        color: MT.ink2,
                      }}
                    >
                      {listing.listing_description}
                    </div>
                  </div>
                ) : null}

                {/* Bullets */}
                {listing.bullet_points.length > 0 ? (
                  <div className="space-y-1.5">
                    <label
                      className="mt-mono text-[10.5px] font-medium uppercase tracking-[0.5px]"
                      style={{ color: MT.ink4 }}
                    >
                      Puntos clave
                    </label>
                    <ol className="space-y-1.5">
                      {listing.bullet_points.map((bp, idx) => (
                        <li
                          key={idx}
                          className="flex gap-2 text-[12.5px]"
                          style={{ color: MT.ink2 }}
                        >
                          <span
                            className="mt-mono shrink-0 text-[11px] font-semibold tabular-nums"
                            style={{ color: MT.brand, paddingTop: 1 }}
                          >
                            {idx + 1}.
                          </span>
                          <span>{bp}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}

                {/* Keywords */}
                {keywords.length > 0 ? (
                  <div className="space-y-2">
                    <label
                      className="mt-mono text-[10.5px] font-medium uppercase tracking-[0.5px]"
                      style={{ color: MT.ink4 }}
                    >
                      Palabras clave
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {keywords.map((kw) => (
                        <span
                          key={kw}
                          className="rounded-[4px] border px-1.5 py-0.5 text-[11px]"
                          style={{
                            borderColor: MT.border,
                            background: MT.surface2,
                            color: MT.ink3,
                          }}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-[12.5px]" style={{ color: MT.ink4 }}>
                Sin contenido generado aún.
              </p>
            )}
          </section>
        </div>

        {/* ── Footer ── */}
        <div
          className="shrink-0 border-t px-5 py-3 flex items-center justify-between gap-3"
          style={{ borderColor: MT.border, background: MT.surface }}
        >
          {/* Confirm overwrite warning */}
          {confirmOverwrite ? (
            <p className="text-[11.5px]" style={{ color: MT.warning }}>
              Ya existe contenido. ¿Sobreescribir?
            </p>
          ) : (
            <span />
          )}

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="text-[12.5px]"
            >
              Cerrar
            </Button>

            <Button
              size="sm"
              disabled={generating}
              onClick={() => void handleGenerate()}
              className="gap-1.5 text-[12.5px]"
              style={{ background: MT.brand, color: "#fff", border: "none" }}
            >
              {generating ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              {confirmOverwrite
                ? "Confirmar sobreescritura"
                : generating
                  ? "Generando…"
                  : "Generar con IA"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
