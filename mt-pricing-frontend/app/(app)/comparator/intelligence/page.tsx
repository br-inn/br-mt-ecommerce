"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { BarChart2, TrendingDown, TrendingUp, Target, AlertTriangle } from "lucide-react";

import { MT } from "@/components/mt/tokens";
import { MtButton } from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { usePriceIntelligenceDashboard, usePriceIntelligenceQuality } from "./_hooks/use-price-intelligence";

// ── Date range presets ─────────────────────────────────────────────────────

const RANGE_PRESETS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

type RangePreset = (typeof RANGE_PRESETS)[number]["days"];

// ── KPI Card ──────────────────────────────────────────────────────────────

interface KpiCardProps {
  title: string;
  value: string | null;
  subtitle?: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
  loading?: boolean;
}

function KpiCard({ title, value, subtitle, icon: Icon, trend, loading }: KpiCardProps) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : null;
  const trendColor = trend === "up" ? MT.success : trend === "down" ? MT.danger : MT.ink3;

  return (
    <div
      className="rounded-xl border p-5 flex flex-col gap-3"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <div className="flex items-start justify-between">
        <span className="text-[12px] font-medium uppercase tracking-[0.5px]" style={{ color: MT.ink3 }}>
          {title}
        </span>
        <Icon className="size-[18px]" style={{ color: MT.ink4 }} />
      </div>
      {loading ? (
        <MtSkeleton className="h-8 w-24" />
      ) : (
        <div className="flex items-end gap-2">
          <span className="text-[28px] font-bold leading-none" style={{ color: MT.ink }}>
            {value ?? "—"}
          </span>
          {TrendIcon && (
            <TrendIcon className="mb-0.5 size-4" style={{ color: trendColor }} />
          )}
        </div>
      )}
      {subtitle && (
        <span className="text-[11px]" style={{ color: MT.ink4 }}>
          {subtitle}
        </span>
      )}
    </div>
  );
}

// ── Histogram Bar ─────────────────────────────────────────────────────────

interface HistogramBarProps {
  bin: string;
  count: number;
  maxCount: number;
}

function HistogramBar({ bin, count, maxCount }: HistogramBarProps) {
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
  const isHigh = bin.startsWith("0.8");

  return (
    <div className="flex flex-col items-center gap-1.5">
      <span className="text-[11px] font-mono" style={{ color: MT.ink3 }}>
        {count}
      </span>
      <div
        className="w-10 rounded-t"
        style={{
          height: `${Math.max(4, pct * 0.8)}px`,
          background: isHigh ? MT.success : MT.brand,
          opacity: isHigh ? 1 : 0.65,
          minHeight: "4px",
        }}
      />
      <span className="text-[9px] text-center leading-tight" style={{ color: MT.ink4 }}>
        {bin}
      </span>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function PriceIntelligencePage() {
  const t = useTranslations("comparator.intelligence");

  const [rangeDays, setRangeDays] = React.useState<RangePreset>(30);
  const [marketplace, setMarketplace] = React.useState<string | "">("");

  const dateFrom = React.useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - rangeDays);
    return d.toISOString();
  }, [rangeDays]);

  const { data: dashboard, isLoading: dashLoading, error: dashError } = usePriceIntelligenceDashboard({
    ...(marketplace ? { marketplace } : {}),
    dateFrom,
  });

  const { data: quality, isLoading: qualLoading, error: qualError } = usePriceIntelligenceQuality();

  const mktStats = dashboard?.market_stats;
  const maxHistCount = React.useMemo(
    () =>
      quality?.histogram
        ? Math.max(...quality.histogram.map((b: { count: number }) => b.count), 1)
        : 1,
    [quality]
  );

  return (
    <RbacGuard permissions={["products:read"]}>
      <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[18px] font-bold" style={{ color: MT.brandDeep }}>
              {t("title")}
            </h1>
            <p className="text-[13px] mt-1" style={{ color: MT.ink3 }}>
              {t("subtitle")}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[12px] font-medium" style={{ color: MT.ink3 }}>
            {t("period")}:
          </span>
          {RANGE_PRESETS.map((p) => (
            <MtButton
              key={p.days}
              tone={rangeDays === p.days ? "primary" : "neutral"}
              size="sm"
              onClick={() => setRangeDays(p.days)}
            >
              {p.label}
            </MtButton>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[12px]" style={{ color: MT.ink3 }}>
              {t("marketplace")}:
            </span>
            <select
              className="text-[12px] rounded-md border px-2 py-1"
              style={{ borderColor: MT.border, background: MT.surface, color: MT.ink }}
              value={marketplace}
              onChange={(e) => setMarketplace(e.target.value)}
            >
              <option value="">{t("allMarketplaces")}</option>
              <option value="amazon_uae">Amazon UAE</option>
              <option value="noon_uae">Noon UAE</option>
            </select>
          </div>
        </div>

        {/* KPI Cards */}
        {dashError ? (
          <MtError message={t("errors.dashboardFailed")} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <KpiCard
              title={t("kpis.marketAvg")}
              value={mktStats?.avg_price_aed != null ? `AED ${mktStats.avg_price_aed.toFixed(2)}` : null}
              subtitle={t("kpis.marketAvgSubtitle")}
              icon={BarChart2}
              loading={dashLoading}
            />
            <KpiCard
              title={t("kpis.marketMin")}
              value={mktStats?.min_price_aed != null ? `AED ${mktStats.min_price_aed.toFixed(2)}` : null}
              subtitle={t("kpis.marketMinSubtitle")}
              icon={TrendingDown}
              trend="down"
              loading={dashLoading}
            />
            <KpiCard
              title={t("kpis.pricePosition")}
              value={
                dashboard?.kpis?.price_position_index != null
                  ? `${dashboard.kpis.price_position_index}%`
                  : null
              }
              subtitle={t("kpis.pricePositionSubtitle")}
              icon={Target}
              loading={dashLoading}
            />
          </div>
        )}

        {/* Matching Quality — Histogram */}
        <div
          className="rounded-xl border p-5"
          style={{ background: MT.surface, borderColor: MT.border }}
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-[14px] font-semibold" style={{ color: MT.ink }}>
                {t("quality.title")}
              </h2>
              <p className="text-[12px]" style={{ color: MT.ink3 }}>
                {t("quality.subtitle")}
              </p>
            </div>
            {quality && (
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-[11px]" style={{ color: MT.ink4 }}>
                    {t("quality.pctAbove80")}
                  </div>
                  <div className="text-[18px] font-bold" style={{ color: MT.success }}>
                    {quality.pct_above_80 != null ? `${quality.pct_above_80.toFixed(1)}%` : "—"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[11px]" style={{ color: MT.ink4 }}>
                    {t("quality.median")}
                  </div>
                  <div className="text-[18px] font-bold" style={{ color: MT.ink }}>
                    {quality.median_confidence != null ? quality.median_confidence.toFixed(2) : "—"}
                  </div>
                </div>
              </div>
            )}
          </div>

          {qualError ? (
            <MtError message={t("errors.qualityFailed")} />
          ) : qualLoading ? (
            <div className="flex items-end gap-3 h-[80px]">
              {Array.from({ length: 5 }).map((_, i) => (
                <MtSkeleton key={i} className="w-10 h-full rounded-t" />
              ))}
            </div>
          ) : quality?.histogram ? (
            <div className="flex items-end gap-3">
              {quality.histogram.map((bar: { bin: string; count: number }) => (
                <HistogramBar
                  key={bar.bin}
                  bin={bar.bin}
                  count={bar.count}
                  maxCount={maxHistCount}
                />
              ))}
              <div className="ml-auto flex items-center gap-1.5" style={{ color: MT.ink4 }}>
                <AlertTriangle className="size-3.5" />
                <span className="text-[11px]">
                  {t("quality.totalMatches", { total: quality.total ?? 0 })}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-[12px]" style={{ color: MT.ink4 }}>
              {t("quality.noData")}
            </p>
          )}
        </div>

        {/* Stats summary */}
        {dashboard && !dashLoading && (
          <div className="rounded-md border px-4 py-3" style={{ borderColor: MT.border, background: MT.surface }}>
            <p className="text-[12px]" style={{ color: MT.ink3 }}>
              {t("summary", {
                records: dashboard.total_records ?? 0,
                dateFrom: new Date(dashboard.date_from).toLocaleDateString(),
                dateTo: new Date(dashboard.date_to).toLocaleDateString(),
              })}
            </p>
          </div>
        )}
      </div>
    </RbacGuard>
  );
}
