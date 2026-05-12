"use client";

/**
 * PricingDashboardClient — observabilidad del workflow de aprobación de precios.
 *
 * US-1B-05-07 · Pantalla "Pricing Approval Dashboard"
 * - KPI cards: pending, auto-aprobados, aprobados hoy, escaladas
 * - Lag promedio de aprobación (últimos 7 días)
 * - Top 3 exception rules
 * - Tendencia diaria 7 días
 *
 * Refresca cada 60s via refetchInterval.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  pricingDashboardApi,
  type DailyPricingTrend,
  type ExceptionRuleHit,
  type PricingDashboardStats,
} from "@/lib/api/endpoints/pricing-dashboard";

// ---- KPI Card ---------------------------------------------------------------

interface KpiCardProps {
  label: string;
  value: string | number;
  accent?: string;
}

function KpiCard({ label, value, accent }: KpiCardProps) {
  return (
    <div
      className="flex flex-col gap-1 rounded-[8px] border p-4"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <span className="text-[11px] uppercase tracking-wide" style={{ color: MT.ink3 }}>
        {label}
      </span>
      <span
        className="mt-mono text-[28px] font-semibold leading-none mt-tnum"
        style={{ color: accent ?? MT.ink }}
      >
        {value}
      </span>
    </div>
  );
}

function KpiCardSkeleton() {
  return (
    <div
      className="flex flex-col gap-2 rounded-[8px] border p-4"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <MtSkeleton width={80} height={11} />
      <MtSkeleton width={56} height={28} />
    </div>
  );
}

// ---- Lag banner -------------------------------------------------------------

interface LagBannerProps {
  hours: number;
  isLoading: boolean;
}

function LagBanner({ hours, isLoading }: LagBannerProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-[8px] border px-4 py-3 text-[13px]"
      style={{ background: MT.brandSoft, borderColor: MT.brandBorder }}
    >
      <span style={{ color: MT.ink3 }}>Lag promedio aprobación (7 días):</span>
      {isLoading ? (
        <MtSkeleton width={60} height={16} />
      ) : (
        <strong className="mt-mono mt-tnum" style={{ color: MT.brand }}>
          {hours.toFixed(1)} h
        </strong>
      )}
    </div>
  );
}

// ---- Top exception rules ----------------------------------------------------

interface TopRulesTableProps {
  rules: ExceptionRuleHit[];
  isLoading: boolean;
}

function TopRulesTable({ rules, isLoading }: TopRulesTableProps) {
  return (
    <div
      className="rounded-[8px] border"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: MT.border }}>
        <span className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: MT.ink2 }}>
          Top Exception Rules (7 días)
        </span>
      </div>
      <div className="divide-y" style={{ borderColor: MT.border }}>
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-3">
              <MtSkeleton width={180} height={14} />
              <MtSkeleton width={40} height={14} />
            </div>
          ))
        ) : rules.length === 0 ? (
          <div className="px-4 py-6 text-center text-[12px]" style={{ color: MT.ink4 }}>
            Sin exception rules disparadas en los últimos 7 días.
          </div>
        ) : (
          rules.map((r) => (
            <div
              key={r.rule_code}
              className="flex items-center justify-between px-4 py-3"
            >
              <div className="flex flex-col gap-0.5">
                <span className="mt-mono text-[12px]" style={{ color: MT.ink }}>
                  {r.rule_code}
                </span>
                {(r.scheme_code ?? r.channel_id) && (
                  <span className="text-[11px]" style={{ color: MT.ink4 }}>
                    {[r.scheme_code, r.channel_id].filter(Boolean).join(" / ")}
                  </span>
                )}
              </div>
              <span
                className="mt-mono mt-tnum text-[13px] font-semibold"
                style={{ color: MT.warning }}
              >
                {r.count} ×
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---- Daily trend table ------------------------------------------------------

interface TrendTableProps {
  rows: DailyPricingTrend[];
  isLoading: boolean;
}

function TrendTable({ rows, isLoading }: TrendTableProps) {
  return (
    <div
      className="rounded-[8px] border"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <div className="px-4 py-3 border-b" style={{ borderColor: MT.border }}>
        <span className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: MT.ink2 }}>
          Tendencia 7 días
        </span>
      </div>
      <table className="w-full text-[12px]">
        <thead>
          <tr style={{ borderBottom: `1px solid ${MT.border}` }}>
            <th className="px-4 py-2 text-left font-medium" style={{ color: MT.ink3 }}>Fecha</th>
            <th className="px-4 py-2 text-right font-medium" style={{ color: MT.ink3 }}>Auto-aprobados</th>
            <th className="px-4 py-2 text-right font-medium" style={{ color: MT.ink3 }}>Aprobados manual</th>
          </tr>
        </thead>
        <tbody className="divide-y" style={{ borderColor: MT.border }}>
          {isLoading ? (
            Array.from({ length: 7 }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-2"><MtSkeleton width={90} height={12} /></td>
                <td className="px-4 py-2 text-right"><MtSkeleton width={40} height={12} /></td>
                <td className="px-4 py-2 text-right"><MtSkeleton width={40} height={12} /></td>
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={3} className="px-4 py-6 text-center" style={{ color: MT.ink4 }}>
                Sin datos de tendencia para los últimos 7 días.
              </td>
            </tr>
          ) : (
            rows.map((r) => (
              <tr key={r.date}>
                <td className="px-4 py-2 mt-mono" style={{ color: MT.ink }}>{r.date}</td>
                <td className="px-4 py-2 text-right mt-mono mt-tnum" style={{ color: MT.success }}>
                  {r.auto_approved}
                </td>
                <td className="px-4 py-2 text-right mt-mono mt-tnum" style={{ color: MT.ink2 }}>
                  {r.manual_approved}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---- Main component ---------------------------------------------------------

export function PricingDashboardClient() {
  const { data, isLoading, isError, error, refetch } = useQuery<PricingDashboardStats>({
    queryKey: ["pricing-dashboard"],
    queryFn: () => pricingDashboardApi.getStats(),
    refetchInterval: 60_000,
  });

  if (isError) {
    return (
      <MtError
        message={error instanceof Error ? error.message : "Error al cargar el dashboard de pricing."}
        onRetry={() => void refetch()}
      />
    );
  }

  const pending = data?.pending_review_count ?? 0;
  const autoApproved = data?.auto_approved_count ?? 0;
  const approvedToday = data?.approved_today_count ?? 0;
  const escalated = data?.escalated_count ?? 0;
  const lagHours = data?.avg_approval_lag_hours ?? 0;
  const topRules = data?.top_exception_rules ?? [];
  const trend = data?.daily_trend ?? [];
  const asOf = data?.as_of;

  const totalApprovedLast7d =
    trend.reduce((acc, d) => acc + d.auto_approved + d.manual_approved, 0) || 1;
  const totalAutoLast7d = trend.reduce((acc, d) => acc + d.auto_approved, 0);
  const autoApprovedPct = Math.round((totalAutoLast7d / totalApprovedLast7d) * 100);

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <KpiCardSkeleton key={i} />)
        ) : (
          <>
            <KpiCard
              label="Pending Review"
              value={pending}
              accent={pending > 0 ? MT.warning : MT.ink}
            />
            <KpiCard
              label={`Auto-aprobados (7d)`}
              value={`${autoApprovedPct}%`}
              accent={MT.success}
            />
            <KpiCard
              label="Aprobados hoy"
              value={approvedToday}
              accent={MT.brand}
            />
            <KpiCard
              label="Escaladas"
              value={escalated}
              accent={escalated > 0 ? MT.danger : MT.ink}
            />
          </>
        )}
      </div>

      {/* Lag banner */}
      <LagBanner hours={lagHours} isLoading={isLoading} />

      {/* Top exception rules + trend */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TopRulesTable rules={topRules} isLoading={isLoading} />
        <TrendTable rows={trend} isLoading={isLoading} />
      </div>

      {/* Timestamp */}
      {asOf && (
        <p className="text-right text-[11px]" style={{ color: MT.ink4 }}>
          Actualizado: {new Date(asOf).toLocaleString("es-AE")}
        </p>
      )}
    </div>
  );
}
