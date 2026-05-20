"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, RefreshCw, ExternalLink, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AlertTriangle } from "lucide-react";

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
  const { data: coverage } = useCoverageStats(brandId, marketplace);

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
  const alertActive = coverage?.alert_active ?? false;
  const alertTooltip = alertActive
    ? t("alertBadgeTooltip", { delta: Math.round(Math.abs(coverage!.delta_pp)) })
    : undefined;

  return (
    <div className="flex items-center gap-1">
      <Badge variant="outline" className={`text-xs ${cls}`} title={title}>
        {t("ageDays", { count: days })}
      </Badge>
      {alertActive && (
        <AlertTriangle
          className="h-3.5 w-3.5 text-yellow-500"
          title={alertTooltip ?? ""}
          aria-label={t("alertActive")}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Types — coverage stats
// ---------------------------------------------------------------------------

interface CoverageStats {
  brand_id: string;
  marketplace: string;
  hit_rate_current: number;
  hit_rate_baseline: number;
  delta_pp: number;
  alert_active: boolean;
  alert_id: string | null;
}

// ---------------------------------------------------------------------------
// HitRateGauge — SVG semicircle gauge (AC-1 US-SCR-05-04)
// ---------------------------------------------------------------------------

function gaugeColor(pct: number): string {
  if (pct >= 80) return "#22c55e"; // green-500
  if (pct >= 60) return "#eab308"; // yellow-500
  return "#ef4444";               // red-500
}

function HitRateGauge({ pct, tooltip }: { pct: number; tooltip: string }) {
  // Semicircle: radius=40, stroke=8, viewBox 0 0 100 55
  const r = 40;
  const cx = 50;
  const cy = 50;
  const circumference = Math.PI * r; // half circle arc length
  const filled = (pct / 100) * circumference;
  const color = gaugeColor(pct);

  return (
    <div className="flex flex-col items-center gap-1" title={tooltip}>
      <svg viewBox="0 0 100 55" className="w-24 h-14" aria-label={`${pct}%`}>
        {/* background arc */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* filled arc using stroke-dasharray */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text x="50" y="48" textAnchor="middle" fontSize="13" fontWeight="600" fill={color}>
          {pct}%
        </text>
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hook — coverage stats (US-SCR-05-04)
// ---------------------------------------------------------------------------

export function useCoverageStats(brandId: string, marketplace = "amazon_uae") {
  return useQuery<CoverageStats | null, Error>({
    queryKey: ["extractor-coverage", brandId, marketplace],
    queryFn: async () => {
      const resp = await fetch(
        `/api/v1/competitor-brands/${encodeURIComponent(brandId)}/extractor/coverage-stats?marketplace=${encodeURIComponent(marketplace)}`
      );
      if (resp.status === 404) return null;
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<CoverageStats>;
    },
    staleTime: 60_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Hook — extractor status
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
  const { data: coverage } = useCoverageStats(brandId, marketplace);

  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [regenerating, setRegenerating] = React.useState(false);
  const [resolving, setResolving] = React.useState(false);

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

  const handleResolveAlert = async () => {
    if (!coverage?.alert_id) return;
    setResolving(true);
    try {
      const resp = await fetch(
        `/api/v1/competitor-brands/${encodeURIComponent(brandId)}/extractor/alerts/${encodeURIComponent(coverage.alert_id)}/resolve`,
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await qc.invalidateQueries({ queryKey: ["extractor-coverage", brandId, marketplace] });
      toast.success(t("resolvedSuccess"));
    } catch {
      toast.error(t("resolving"));
    } finally {
      setResolving(false);
    }
  };

  // Has extractor — show details
  const days = daysSince(data.generated_at);
  const light = trafficLight(data.generated_at);
  const cls = trafficLightClass(light);
  const lastUsedDays = data.last_used_at ? daysSince(data.last_used_at) : null;
  const visibleAsins = data.sample_asins.slice(0, 5);
  const hitPct = Math.round(data.hit_rate * 100);
  const alertActive = coverage?.alert_active ?? false;

  return (
    <div className="space-y-4 py-2">
      {/* Alert banner (AC-2 US-SCR-05-04) */}
      {alertActive && coverage && (
        <div className="flex items-center justify-between rounded-md border border-yellow-400/40 bg-yellow-50 px-3 py-2 text-sm">
          <div className="flex items-center gap-2 text-yellow-800">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{t("alertBadgeTooltip", { delta: Math.round(Math.abs(coverage.delta_pp)) })}</span>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs shrink-0"
            onClick={handleResolveAlert}
            disabled={resolving}
          >
            {resolving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
            {resolving ? t("resolving") : t("markResolved")}
          </Button>
        </div>
      )}

      {/* Hit-rate gauge (AC-1 US-SCR-05-04) */}
      <div className="flex flex-col items-center gap-1 py-2">
        <HitRateGauge pct={hitPct} tooltip={t("gaugeTooltip")} />
        <p className="text-xs text-muted-foreground">{t("hitRateGauge")}</p>
      </div>

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
