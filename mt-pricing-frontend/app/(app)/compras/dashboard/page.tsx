"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Ban,
  FileText,
  ShoppingCart,
  TrendingUp,
  Truck,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { procurementKpiApi, type SpendPeriod } from "@/lib/api/endpoints/procurement";

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
  loading = false,
}: {
  title: string;
  value: string | number | null;
  subtitle?: string;
  icon: React.ElementType;
  variant?: "default" | "warning" | "destructive";
  loading?: boolean;
}) {
  const colorMap = {
    default: "text-foreground",
    warning: "text-amber-600 dark:text-amber-400",
    destructive: "text-destructive",
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className={`h-4 w-4 ${colorMap[variant]}`} />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <>
            <p className={`text-2xl font-bold ${colorMap[variant]}`}>
              {value ?? "—"}
            </p>
            {subtitle && (
              <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Simple bar chart (CSS only — no external chart library)
// ---------------------------------------------------------------------------

interface BarItem {
  label: string;
  value: number;
}

function SimpleBarChart({
  data,
  formatValue,
}: {
  data: BarItem[];
  formatValue?: (v: number) => string;
}) {
  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        Sin datos para el período seleccionado
      </div>
    );
  }

  const max = Math.max(...data.map((d) => d.value));
  const fmt = formatValue ?? ((v) => v.toLocaleString("es-AE"));

  return (
    <div className="space-y-2">
      {data.map((item) => {
        const pct = max > 0 ? (item.value / max) * 100 : 0;
        return (
          <div key={item.label} className="flex items-center gap-2">
            <span
              className="w-24 shrink-0 truncate text-right text-xs text-muted-foreground"
              title={item.label}
            >
              {item.label}
            </span>
            <div className="relative h-5 flex-1 rounded bg-muted">
              <div
                className="h-full rounded bg-primary transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-24 shrink-0 text-right text-xs font-mono">
              {fmt(item.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ProcurementDashboardPage() {
  const [period, setPeriod] = React.useState<SpendPeriod>("30d");

  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["procurement-kpis"],
    queryFn: () => procurementKpiApi.kpis(),
    staleTime: 60_000,
  });

  const { data: spend, isLoading: spendLoading } = useQuery({
    queryKey: ["procurement-spend", period],
    queryFn: () => procurementKpiApi.spendAnalysis(period),
    staleTime: 60_000,
  });

  const vendorChartData: BarItem[] = (spend?.by_vendor ?? []).map((v) => ({
    label: v.vendor_id.slice(0, 16),
    value: Number(v.total_amount),
  }));

  const productChartData: BarItem[] = (spend?.by_product ?? []).map((p) => ({
    label: p.product_sku.slice(0, 16),
    value: Number(p.total_amount),
  }));

  const fmtAmount = (v: number) =>
    `AED ${v.toLocaleString("es-AE", { minimumFractionDigits: 0 })}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Dashboard de Compras
        </h1>
        <p className="text-sm text-muted-foreground">
          KPIs del módulo P2P y análisis de gasto
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <KpiCard
          title="PRs abiertas"
          value={kpis?.open_pr_count ?? null}
          icon={FileText}
          loading={kpisLoading}
          subtitle="pending_approval + approved"
        />
        <KpiCard
          title="POs abiertas"
          value={kpis?.open_po_count ?? null}
          icon={ShoppingCart}
          loading={kpisLoading}
          subtitle="confirmed + partial"
        />
        <KpiCard
          title="Facturas pendientes"
          value={kpis?.pending_invoice_count ?? null}
          icon={FileText}
          variant={
            kpis && kpis.pending_invoice_count > 10 ? "warning" : "default"
          }
          loading={kpisLoading}
          subtitle="pending + blocked"
        />
        <KpiCard
          title="Importe bloqueado"
          value={
            kpis
              ? `AED ${Number(kpis.blocked_invoice_amount).toLocaleString(
                  "es-AE",
                  { minimumFractionDigits: 2 },
                )}`
              : null
          }
          icon={Ban}
          variant={
            kpis && Number(kpis.blocked_invoice_amount) > 0
              ? "destructive"
              : "default"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title="Maverick spend"
          value={
            kpis
              ? `${Number(kpis.maverick_spend_pct).toFixed(1)} %`
              : null
          }
          icon={AlertCircle}
          variant={
            kpis && Number(kpis.maverick_spend_pct) > 10 ? "warning" : "default"
          }
          loading={kpisLoading}
          subtitle="compras sin PO"
        />
        <KpiCard
          title="Lead time promedio PO"
          value={
            kpis?.avg_po_lead_time_days != null
              ? `${Number(kpis.avg_po_lead_time_days).toFixed(1)} días`
              : null
          }
          icon={Truck}
          loading={kpisLoading}
          subtitle="entre PO confirmada y GR"
        />
        <KpiCard
          title="Entregas a tiempo"
          value={
            kpis?.on_time_delivery_pct != null
              ? `${Number(kpis.on_time_delivery_pct).toFixed(1)} %`
              : "N/D"
          }
          icon={TrendingUp}
          loading={kpisLoading}
        />
      </div>

      {/* Spend Analysis */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Análisis de gasto</h2>
        <Select
          value={period}
          onValueChange={(v) => setPeriod(v as SpendPeriod)}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30d">30 días</SelectItem>
            <SelectItem value="90d">90 días</SelectItem>
            <SelectItem value="365d">365 días</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* By Vendor */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Top 10 proveedores por gasto
            </CardTitle>
          </CardHeader>
          <CardContent>
            {spendLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-5 w-full" />
                ))}
              </div>
            ) : (
              <SimpleBarChart data={vendorChartData} formatValue={fmtAmount} />
            )}
          </CardContent>
        </Card>

        {/* By Product */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Top 10 productos por gasto
            </CardTitle>
          </CardHeader>
          <CardContent>
            {spendLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-5 w-full" />
                ))}
              </div>
            ) : (
              <SimpleBarChart data={productChartData} formatValue={fmtAmount} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
