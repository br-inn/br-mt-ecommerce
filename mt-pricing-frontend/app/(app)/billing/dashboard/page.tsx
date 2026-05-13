"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Clock,
  DollarSign,
  FileText,
  TrendingDown,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  billingApi,
  type InvoiceRead,
  type InvoiceStatus,
  type ARAgingBucket,
} from "@/lib/api/endpoints/billing";

// ---------------------------------------------------------------------------
// Status badge config
// ---------------------------------------------------------------------------

const STATUS_META: Record<
  InvoiceStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft: { label: "Borrador", variant: "secondary" },
  posted: { label: "Posteado", variant: "default" },
  cancelled: { label: "Cancelado", variant: "destructive" },
  reversed: { label: "Revertido", variant: "outline" },
};

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

interface KpiCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  description?: string;
  variant?: "default" | "warning" | "danger";
}

function KpiCard({
  title,
  value,
  icon: Icon,
  description,
  variant = "default",
}: KpiCardProps) {
  const iconColors = {
    default: "text-primary",
    warning: "text-yellow-500",
    danger: "text-destructive",
  };
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={`size-4 ${iconColors[variant]}`} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description ? (
          <p className="text-xs text-muted-foreground">{description}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// AR Aging mini-table
// ---------------------------------------------------------------------------

function AgingTable({ buckets }: { buckets: ARAgingBucket[] }) {
  if (buckets.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        Sin cuentas por cobrar abiertas.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Cliente</TableHead>
          <TableHead className="text-right">Vigente</TableHead>
          <TableHead className="text-right">1-30 d</TableHead>
          <TableHead className="text-right">31-60 d</TableHead>
          <TableHead className="text-right">61-90 d</TableHead>
          <TableHead className="text-right">+90 d</TableHead>
          <TableHead className="text-right">Total</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {buckets.slice(0, 10).map((b) => (
          <TableRow key={b.customer_id}>
            <TableCell className="font-mono text-xs">{b.customer_id}</TableCell>
            <TableCell className="text-right text-xs">
              {Number(b.current).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
            <TableCell className="text-right text-xs text-yellow-600">
              {Number(b.days_1_30).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
            <TableCell className="text-right text-xs text-orange-600">
              {Number(b.days_31_60).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
            <TableCell className="text-right text-xs text-red-500">
              {Number(b.days_61_90).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
            <TableCell className="text-right text-xs text-red-700 font-semibold">
              {Number(b.days_90_plus).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
            <TableCell className="text-right text-xs font-bold">
              {Number(b.total_outstanding).toLocaleString("es-AE", { minimumFractionDigits: 2 })}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Overdue Invoices table
// ---------------------------------------------------------------------------

function OverdueTable({ invoices }: { invoices: InvoiceRead[] }) {
  if (invoices.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        Sin facturas vencidas.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Nro. Factura</TableHead>
          <TableHead>Cliente</TableHead>
          <TableHead>Vencimiento</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead>Estado</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {invoices.map((inv) => {
          const meta = STATUS_META[inv.status];
          return (
            <TableRow key={inv.id}>
              <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
              <TableCell className="text-xs">{inv.customer_id}</TableCell>
              <TableCell className="text-xs">
                {inv.due_date ?? "—"}
              </TableCell>
              <TableCell className="text-xs">{inv.invoice_type}</TableCell>
              <TableCell className="text-right text-xs font-semibold">
                {inv.total_amount
                  ? Number(inv.total_amount).toLocaleString("es-AE", {
                      minimumFractionDigits: 2,
                    })
                  : "—"}{" "}
                {inv.currency}
              </TableCell>
              <TableCell>
                <Badge variant={meta.variant}>{meta.label}</Badge>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BillingDashboardPage() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["billing-kpis"],
    queryFn: () => billingApi.getKpis(),
    refetchInterval: 60_000,
  });

  const { data: aging, isLoading: agingLoading } = useQuery({
    queryKey: ["billing-ar-aging"],
    queryFn: () => billingApi.getArAging(),
    refetchInterval: 120_000,
  });

  const { data: overdueInvoices, isLoading: overdueLoading } = useQuery({
    queryKey: ["billing-overdue-invoices"],
    queryFn: () =>
      billingApi.listInvoices({ status: "posted", limit: 20, offset: 0 }),
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Dashboard Billing</h1>
        <p className="text-sm text-muted-foreground">
          KPIs de facturación, cuentas por cobrar y vencimientos
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {kpisLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-24" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <KpiCard
              title="DSO (Days Sales Outstanding)"
              value={kpis?.dso ? `${Number(kpis.dso).toFixed(1)} días` : "—"}
              icon={Clock}
              description="Días promedio de cobro"
              variant={
                kpis?.dso && Number(kpis.dso) > 45
                  ? "danger"
                  : kpis?.dso && Number(kpis.dso) > 30
                  ? "warning"
                  : "default"
              }
            />
            <KpiCard
              title="CEI (Collection Effectiveness)"
              value={kpis?.cei ? `${Number(kpis.cei).toFixed(1)}%` : "—"}
              icon={TrendingDown}
              description="Efectividad de cobranza 30d"
            />
            <KpiCard
              title="Tiempo a Factura (avg)"
              value={
                kpis?.time_to_invoice_avg_hours
                  ? `${Number(kpis.time_to_invoice_avg_hours).toFixed(1)}h`
                  : "—"
              }
              icon={FileText}
              description="Desde despacho hasta factura"
              variant={
                kpis?.time_to_invoice_avg_hours &&
                Number(kpis.time_to_invoice_avg_hours) > 24
                  ? "warning"
                  : "default"
              }
            />
            <KpiCard
              title="Compliance e-Invoice"
              value={
                kpis?.e_invoice_compliance_pct
                  ? `${Number(kpis.e_invoice_compliance_pct).toFixed(1)}%`
                  : "—"
              }
              icon={BarChart3}
              description="Facturas electrónicas aceptadas"
              variant={
                kpis?.e_invoice_compliance_pct &&
                Number(kpis.e_invoice_compliance_pct) < 95
                  ? "warning"
                  : "default"
              }
            />
            <KpiCard
              title="Facturas Vencidas"
              value={kpis?.overdue_invoice_count ?? 0}
              icon={AlertTriangle}
              description="Pendientes de cobro"
              variant={
                (kpis?.overdue_invoice_count ?? 0) > 0 ? "danger" : "default"
              }
            />
            <KpiCard
              title="Monto Vencido"
              value={
                kpis?.overdue_amount
                  ? `AED ${Number(kpis.overdue_amount).toLocaleString("es-AE", {
                      minimumFractionDigits: 2,
                    })}`
                  : "AED 0.00"
              }
              icon={DollarSign}
              description="Suma de facturas vencidas"
              variant={
                kpis?.overdue_amount && Number(kpis.overdue_amount) > 0
                  ? "danger"
                  : "default"
              }
            />
          </>
        )}
      </div>

      {/* AR Aging */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">AR Aging — Cuentas por Cobrar</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {agingLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <AgingTable buckets={aging?.buckets ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Overdue Invoices */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Facturas Vencidas</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {overdueLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <OverdueTable
              invoices={(overdueInvoices ?? []).filter(
                (inv) =>
                  inv.due_date !== null && new Date(inv.due_date) < new Date()
              )}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
