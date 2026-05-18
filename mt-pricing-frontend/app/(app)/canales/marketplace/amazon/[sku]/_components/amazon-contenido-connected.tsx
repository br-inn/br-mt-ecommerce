"use client";

import * as React from "react";
import { toast } from "sonner";
import { Loader2, Sparkles, Save } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MT } from "@/components/mt/tokens";
import {
  marketplaceListingsApi,
  type MarketplaceListingRead,
} from "@/lib/api/endpoints/marketplace-listings";

interface Props {
  sku: string;
}

export function AmazonContenidoConnected({ sku }: Props) {
  const [listing, setListing] = React.useState<MarketplaceListingRead | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  // Local editable state (strings)
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [bullets, setBullets] = React.useState<string[]>(["", "", "", "", ""]);
  const [keywords, setKeywords] = React.useState("");

  const [isSaving, setIsSaving] = React.useState(false);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = React.useState(false);

  // -------------------------------------------------------------------------
  // Load listing
  // -------------------------------------------------------------------------
  React.useEffect(() => {
    setIsLoading(true);
    marketplaceListingsApi
      .getListing(sku)
      .then((data) => {
        setListing(data);
        setTitle(data.listing_title ?? "");
        setDescription(data.listing_description ?? "");
        const bp = [...data.bullet_points];
        while (bp.length < 5) bp.push("");
        setBullets(bp.slice(0, 5));
        setKeywords(data.search_keywords ?? "");
      })
      .catch(() => {
        // 404 = no listing yet; start with empty form
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [sku]);

  // -------------------------------------------------------------------------
  // Save
  // -------------------------------------------------------------------------
  const handleSave = React.useCallback(async () => {
    setIsSaving(true);
    try {
      const result = await marketplaceListingsApi.upsertListing(sku, {
        listing_title: title.trim() || null,
        listing_description: description.trim() || null,
        bullet_points: bullets.map((b) => b.trim()).filter(Boolean),
        search_keywords: keywords.trim() || null,
        status: listing?.status ?? "draft",
      });
      setListing(result);
      toast.success("Cambios guardados");
    } catch (err) {
      toast.error("No se pudo guardar", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsSaving(false);
    }
  }, [sku, title, description, bullets, keywords, listing]);

  // -------------------------------------------------------------------------
  // Generate
  // -------------------------------------------------------------------------
  const hasContent = !!(listing?.listing_title || listing?.listing_description || listing?.bullet_points.length);

  const handleGenerate = React.useCallback(async () => {
    if (hasContent && !confirmOverwrite) {
      setConfirmOverwrite(true);
      return;
    }
    setIsGenerating(true);
    setConfirmOverwrite(false);
    try {
      const result = await marketplaceListingsApi.generateListing(sku, hasContent);
      setListing(result);
      setTitle(result.listing_title ?? "");
      setDescription(result.listing_description ?? "");
      const bp = [...result.bullet_points];
      while (bp.length < 5) bp.push("");
      setBullets(bp.slice(0, 5));
      setKeywords(result.search_keywords ?? "");
      toast.success(`Listing generado con IA para ${sku}`);
    } catch (err) {
      toast.error("Error al generar", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsGenerating(false);
    }
  }, [sku, hasContent, confirmOverwrite]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle className="text-base">Contenido del Listing</CardTitle>
            <CardDescription>
              Editá el contenido que se publicará en Amazon UAE. Los campos son editables.
            </CardDescription>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {confirmOverwrite ? (
              <span className="text-[11.5px]" style={{ color: MT.warning }}>
                Ya existe contenido. ¿Sobreescribir?
              </span>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              disabled={isGenerating}
              onClick={() => void handleGenerate()}
              className="gap-1.5"
            >
              {isGenerating ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              {confirmOverwrite ? "Confirmar" : isGenerating ? "Generando…" : "Generar con IA"}
            </Button>
            <Button
              size="sm"
              disabled={isSaving}
              onClick={() => void handleSave()}
              className="gap-1.5"
            >
              {isSaving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              {isSaving ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          {/* Título */}
          <div className="space-y-1.5">
            <label className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
              Título <span className="normal-case">(máx. 200 chars)</span>
            </label>
            <input
              type="text"
              maxLength={200}
              value={title}
              onChange={(e) => { setTitle(e.target.value); setConfirmOverwrite(false); }}
              placeholder="Título del producto en Amazon…"
              className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-right text-[11px] text-muted-foreground">{title.length}/200</p>
          </div>

          {/* Descripción */}
          <div className="space-y-1.5">
            <label className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
              Descripción <span className="normal-case">(máx. 2000 chars)</span>
            </label>
            <textarea
              maxLength={2000}
              rows={6}
              value={description}
              onChange={(e) => { setDescription(e.target.value); setConfirmOverwrite(false); }}
              placeholder="Descripción del producto…"
              className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring resize-y"
            />
            <p className="text-right text-[11px] text-muted-foreground">{description.length}/2000</p>
          </div>

          {/* Bullet points */}
          <div className="space-y-2">
            <label className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
              Puntos clave <span className="normal-case">(hasta 5)</span>
            </label>
            <div className="space-y-2">
              {bullets.map((bp, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span
                    className="shrink-0 text-[11px] font-semibold tabular-nums"
                    style={{ color: MT.brand, width: 16, textAlign: "center" }}
                  >
                    {idx + 1}.
                  </span>
                  <input
                    type="text"
                    value={bp}
                    onChange={(e) => {
                      const next = [...bullets];
                      next[idx] = e.target.value;
                      setBullets(next);
                      setConfirmOverwrite(false);
                    }}
                    placeholder={`Punto clave ${idx + 1}…`}
                    className="flex-1 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Keywords */}
          <div className="space-y-1.5">
            <label className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
              Palabras clave <span className="normal-case">(separadas por coma)</span>
            </label>
            <textarea
              maxLength={500}
              rows={3}
              value={keywords}
              onChange={(e) => { setKeywords(e.target.value); setConfirmOverwrite(false); }}
              placeholder="valve, brass valve, ball valve UAE…"
              className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </div>

          {/* AI metadata */}
          {listing?.ai_generated_at ? (
            <p className="text-[11px] text-muted-foreground">
              Generado con IA{listing.ai_model ? ` (${listing.ai_model})` : ""} el{" "}
              {new Date(listing.ai_generated_at).toLocaleString("es-ES", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
