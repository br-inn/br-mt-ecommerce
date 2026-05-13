"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Package,
  RefreshCcw,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  type InventoryKpisRead,
  type ProductAbcClassificationRead,
  inventoryApi,
} from "@/lib/api/endpoints/inventory";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDecimal(v: string | null | undefined, decimals = 2): string {
  if (v === null || v === undefined) return "—";
  const n = parseFloat(v);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("en-AE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtPct(v: string | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const n = parseFloat(v);
  if (Number.isNaN(n)) return "—";
  return `${n.toFixed(1)}%`;
}

function abcBadgeVariant(cls: string): "default" | "secondary" | "outline" {
  if (cls === "A") return "default";
  if (cls === "B") return "secondary";
  return "outline";
}

// ---------------------------------------------------------------------------
// KPI Card component
// ---------------------------------------------------------------------------

interface KpiCardProps {
  title: string;
  value: React.ReactNode;
  description?: string;
  icon: React.ReactNode;
  status?: "ok" | "warning" | "critical" | "neutral";
  loading?: boolean;
}

function KpiCard({ title, value, description, icon, status = "neutral", loading }: KpiCardProps) {
  const statusColor = {
    ok: "text-emerald-600",
    warning: "text-amber-500",
    critical: "text-red-500",
    neutral: "text-muted-foreground",
  }[status];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <span className={statusColor}>{icon}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className={`text-2xl font-bold tabular-nums ${statusColor}`}>{value}</p>
        )}
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function InventarioKpisPage() {
  const t = useTranslations("admin.inventario.kpis");

  const {
    data: kpis,
    isLoading: kpisLoading,
    isError: kpisError,
    refetch: refetchKpis,
  } = useQuery<InventoryKpisRead>({
    queryKey: ["inventory-kpis"],
    queryFn: () => inventoryApi.getKpis(),
    staleTime: 2 * 60_000,
    refetchInterval: 5 * 60_000,
  });

  const { data: abcData, isLoading: abcLoading } = useQuery<ProductAbcClassificationRead[]>({
    queryKey: ["inventory-abc-classifications"],
    queryFn: () => inventoryApi.listAbcClassifications({ abc_class: "A" }),
    staleTime: 10 * 60_000,
  });

  const computedAt = kpis?.computed_at
    ? new Intl.DateTimeFormat("es-AE", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(kpis.computed_at))
    : null;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">
            {computedAt ? `${t("computedAt")} ${computedAt}` : t("subtitle")}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void refetchKpis()}
          disabled={kpisLoading}
        >
          <RefreshCcw className={`size-4 ${kpisLoading ? "animate-spin" : ""}`} />
          {t("refresh")}
        </Button>
      </div>

      {kpisError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {t("loadError")}
        </div>
      )}

      {/* KPI Cards — 6 métricas */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <KpiCard
          title={t("turnoverTitle")}
          value={kpis ? fmtDecimal(kpis.inventory_turnover) : "—"}
          description={t("turnoverDesc")}
          icon={<TrendingUp className="size-4" />}
          status={
            kpis?.inventory_turnover
              ? parseFloat(kpis.inventory_turnover) >= 4
                ? "ok"
                : "warning"
              : "neutral"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title={t("dohTitle")}
          value={kpis ? fmtDecimal(kpis.days_on_hand, 1) : "—"}
          description={t("dohDesc")}
          icon={<Clock className="size-4" />}
          status={
            kpis?.days_on_hand
              ? parseFloat(kpis.days_on_hand) <= 90
                ? "ok"
                : "warning"
              : "neutral"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title={t("fillRateTitle")}
          value={fmtPct(kpis?.fill_rate_pct)}
          description={t("fillRateDesc")}
          icon={<CheckCircle2 className="size-4" />}
          status={
            kpis?.fill_rate_pct
              ? parseFloat(kpis.fill_rate_pct) >= 95
                ? "ok"
                : "warning"
              : "neutral"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title={t("stockoutTitle")}
          value={kpis?.stockout_count ?? "—"}
          description={t("stockoutDesc")}
          icon={<TrendingDown className="size-4" />}
          status={
            kpis
              ? kpis.stockout_count === 0
                ? "ok"
                : kpis.stockout_count <= 5
                  ? "warning"
                  : "critical"
              : "neutral"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title={t("expiryAlertTitle")}
          value={kpis?.expiry_alert_count ?? "—"}
          description={t("expiryAlertDesc")}
          icon={<AlertTriangle className="size-4" />}
          status={
            kpis
              ? kpis.expiry_alert_count === 0
                ? "ok"
                : kpis.expiry_alert_count <= 10
                  ? "warning"
                  : "critical"
              : "neutral"
          }
          loading={kpisLoading}
        />
        <KpiCard
          title={t("ropBreachTitle")}
          value={kpis?.rop_breach_count ?? "—"}
          description={t("ropBreachDesc")}
          icon={<Package className="size-4" />}
          status={
            kpis
              ? kpis.rop_breach_count === 0
                ? "ok"
                : kpis.rop_breach_count <= 5
                  ? "warning"
                  : "critical"
              : "neutral"
          }
          loading={kpisLoading}
        />
      </div>

      {/* Tabla de productos clase A (stock crítico) */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4 text-muted-foreground" />
            <CardTitle className="text-base">{t("abcTableTitle")}</CardTitle>
          </div>
          <CardDescription>{t("abcTableDesc")}</CardDescription>
        </CardHeader>
        <CardContent>
          {abcLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : !abcData || abcData.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              {t("abcEmpty")}
            </p>
          ) : (
            <div className="overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("colSku")}</TableHead>
                    <TableHead>{t("colClass")}</TableHead>
                    <TableHead className="text-right">{t("colValue")}</TableHead>
                    <TableHead className="text-right">{t("colPct")}</TableHead>
                    <TableHead>{t("colClassifiedAt")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {abcData.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="font-mono text-xs">{row.product_sku}</TableCell>
                      <TableCell>
                        <Badge variant={abcBadgeVariant(row.abc_class)}>
                          {row.abc_class}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        AED {fmtDecimal(row.annual_consumption_value)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {fmtDecimal(row.pct_of_total, 2)}%
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(row.classified_at).toLocaleDateString("es-AE")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
