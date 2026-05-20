"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, RefreshCw, ExternalLink, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExtractorStatus {
  brand_id: string;
  marketplace: string;
  generated_at: string;
  generated_by: string;
  hit_rate: number;
  sample_asins: string[];
  attribute_count: number;
  last_used_at: string | null;
}

export interface ExtractorPanelProps {
  brandId: string;
  marketplace?: string;
  onRegenerate?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function daysSince(iso: string): number {
  const ms = Date.now() - new Date(iso).getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

function formatLocalDate(iso: string): string {
  return new Date(iso).toLocaleString("es-AE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type TrafficLight = "green" | "yellow" | "red";

function trafficLight(generatedAt: string): TrafficLight {
  const days = daysSince(generatedAt);
  if (days < 30) return "green";
  if (days <= 90) return "yellow";
  return "red";
}

function trafficLightClass(light: TrafficLight): string {
  switch (light) {
    case "green":
      return "border-green-500/40 text-green-700 bg-green-50";
    case "yellow":
      return "border-yellow-500/40 text-yellow-700 bg-yellow-50";
    case "red":
      return "border-red-500/40 text-red-700 bg-red-50";
  }
}

// ---------------------------------------------------------------------------
// Extractor status badge (used in the table column)
// ---------------------------------------------------------------------------

interface ExtractorBadgeProps {
  brandId: string;
  marketplace?: string;
}

export function ExtractorBadge({
  brandId,
  marketplace = "amazon_uae",
}: ExtractorBadgeProps) {
  const t = useTranslations("admin.brandExtractor");
  const { data, isLoading } = useExtractorStatus(brandId, marketplace);

  if (isLoading) {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />;
  }

  if (!data) {
    return (
      <Badge variant="outline" className="text-muted-foreground text-xs">
        {t("noExtractor")}
      </Badge>
    );
  }

  const days = daysSince(data.generated_at);
  const light = trafficLight(data.generated_at);
  const cls = trafficLightClass(light);
  const title = formatLocalDate(data.generated_at);

  return (
    <Badge
      variant="outline"
      className={`text-xs ${cls}`}
      title={title}
    >
      {t("ageDays", { count: days })}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useExtractorStatus(brandId: string, marketplace = "amazon_uae") {
  return useQuery<ExtractorStatus | null, Error>({
    queryKey: ["extractor-status", brandId, marketplace],
    queryFn: async () => {
      const resp = await fetch(
        `/api/v1/competitor-brands/${encodeURIComponent(brandId)}/extractor?marketplace=${encodeURIComponent(marketplace)}`
      );
      if (resp.status === 404) return null;
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<ExtractorStatus>;
    },
    staleTime: 60_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// ExtractorPanel
// ---------------------------------------------------------------------------

export function ExtractorPanel({
  brandId,
  marketplace = "amazon_uae",
  onRegenerate,
}: ExtractorPanelProps) {
  const t = useTranslations("admin.brandExtractor");
  const qc = useQueryClient();

  const { data, isLoading, error } = useExtractorStatus(brandId, marketplace);

  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [regenerating, setRegenerating] = React.useState(false);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const resp = await fetch(
        `/api/v1/competitor-brands/${encodeURIComponent(brandId)}/bootstrap-scan?marketplace=${encodeURIComponent(marketplace)}`,
        { method: "POST" }
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await qc.invalidateQueries({
        queryKey: ["extractor-status", brandId, marketplace],
      });
      const msg = data
        ? t("regenerateSuccess")
        : t("regenerateSuccess");
      toast.success(msg);
      onRegenerate?.();
    } catch {
      toast.error(t("regenerating"));
    } finally {
      setRegenerating(false);
      setConfirmOpen(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("noExtractorMessage")}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-6 text-sm text-destructive">
        Error al cargar el extractor.
      </div>
    );
  }

  // No extractor (404)
  if (!data) {
    return (
      <div className="flex flex-col items-center gap-4 py-10 text-center">
        <Zap className="h-10 w-10 text-muted-foreground/40" />
        <div>
          <p className="text-sm font-medium">{t("noExtractorMessage")}</p>
          <p className="text-xs text-muted-foreground mt-1">
            marketplace: {marketplace}
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setConfirmOpen(true)}
          disabled={regenerating}
          className="gap-1.5"
        >
          {regenerating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="h-3.5 w-3.5" />
          )}
          {regenerating ? t("regenerating") : t("generate")}
        </Button>

        <ConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          title={t("confirmTitle")}
          description={t("confirmRegenerate")}
          confirmLabel={regenerating ? t("regenerating") : t("generate")}
          busy={regenerating}
          onConfirm={handleRegenerate}
        />
      </div>
    );
  }

  // Has extractor — show details
  const days = daysSince(data.generated_at);
  const light = trafficLight(data.generated_at);
  const cls = trafficLightClass(light);
  const lastUsedDays = data.last_used_at ? daysSince(data.last_used_at) : null;
  const visibleAsins = data.sample_asins.slice(0, 5);

  return (
    <div className="space-y-4 py-2">
      {/* Status header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={`text-xs ${cls}`}>
            {t("ageDays", { count: days })}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {t("generatedAt")}: {formatLocalDate(data.generated_at)}
          </span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setConfirmOpen(true)}
          disabled={regenerating}
          className="h-7 gap-1.5 text-xs"
        >
          {regenerating ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          {regenerating ? t("regenerating") : t("regenerate")}
        </Button>
      </div>

      {/* Metadata grid */}
      <div className="rounded-md border divide-y text-sm">
        {/* Model */}
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-muted-foreground">{t("generatedBy")}</span>
          <span className="font-mono text-xs">{data.generated_by}</span>
        </div>

        {/* Hit rate */}
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-muted-foreground">{t("hitRate")}</span>
          <span className="font-medium">
            {t("coveragePct", { pct: Math.round(data.hit_rate * 100) })}
          </span>
        </div>

        {/* Attribute count */}
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-muted-foreground">Atributos</span>
          <span className="font-medium">
            {t("attributeCount", { count: data.attribute_count })}
          </span>
        </div>

        {/* Last used */}
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-muted-foreground">{t("lastUsedAt")}</span>
          <span>
            {lastUsedDays !== null
              ? t("ageDays", { count: lastUsedDays })
              : t("neverUsed")}
          </span>
        </div>
      </div>

      {/* Sample ASINs */}
      {visibleAsins.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            {t("sampleAsins")}
          </p>
          <ul className="space-y-1">
            {visibleAsins.map((asin) => (
              <li key={asin}>
                <a
                  href={`https://www.amazon.ae/dp/${asin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-primary hover:underline font-mono"
                >
                  {asin}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confirm regenerate dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("confirmTitle")}
        description={t("confirmRegenerate")}
        confirmLabel={regenerating ? t("regenerating") : t("regenerate")}
        busy={regenerating}
        onConfirm={handleRegenerate}
      />
    </div>
  );
}
