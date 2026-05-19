"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Package,
  ShoppingCart,
  TrendingUp,
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
import { salesApi, type SOStatus, type SalesOrderRead } from "@/lib/api/endpoints/sales";

// ---------------------------------------------------------------------------
// Status badge config
// ---------------------------------------------------------------------------

const STATUS_META: Record<SOStatus, { label: string; variant: string }> = {
  draft: { label: "Borrador", variant: "secondary" },
  confirmed: { label: "Confirmado", variant: "default" },
  in_fulfillment: { label: "En preparación", variant: "default" },
  partially_delivered: { label: "Parcial", variant: "warning" },
  delivered: { label: "Entregado", variant: "success" },
  invoiced: { label: "Facturado", variant: "success" },
  closed: { label: "Cerrado", variant: "outline" },
  cancelled: { label: "Cancelado", variant: "destructive" },
  on_credit_hold: { label: "Crédito bloqueado", variant: "destructive" },
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

function KpiCard({ title, value, icon: Icon, description, variant = "default" }: KpiCardProps) {
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
// Page
// ---------------------------------------------------------------------------

export default function VentasDashboardPage() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["sales-kpis"],
    queryFn: () => salesApi.getKpis(),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  const { data: backorders, isLoading: backordersLoading } = useQuery({
    queryKey: ["sales-backorders"],
    queryFn: () => salesApi.getBackorders(20),
    staleTime: 30_000,
  });

  const { data: recentSOs, isLoading: sosLoading } = useQuery({
    queryKey: ["sales-orders-recent"],
    queryFn: () => salesApi.listOrders({ limit: 10, offset: 0 }),
    staleTime: 30_000,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard Ventas O2C</h1>
        <p className="text-sm text-muted-foreground">
          Indicadores clave del ciclo Order-to-Cash
        </p>
      </header>

      {/* KPI Cards */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {kpisLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-12 w-full" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <KpiCard
              title="Pedidos abiertos"
              value={kpis?.open_so_count ?? 0}
              icon={ShoppingCart}
              description="Confirmados + en preparación + parciales"
            />
            <KpiCard
              title="Líneas en backorder"
              value={kpis?.backorder_count ?? 0}
              icon={Clock}
              variant={kpis && kpis.backorder_count > 0 ? "warning" : "default"}
              description="Líneas sin stock confirmado"
            />
            <KpiCard
              title="OTD % (últimos 30d)"
              value={`${kpis?.on_time_delivery_pct?.toFixed(1) ?? "0.0"}%`}
              icon={CheckCircle2}
              variant={
                kpis && kpis.on_time_delivery_pct < 80
                  ? "warning"
                  : "default"
              }
              description="Entregas a tiempo vs. fecha solicitada"
            />
            <KpiCard
              title="Valor medio pedido"
              value={
                kpis
                  ? `AED ${parseFloat(kpis.avg_order_value).toLocaleString("es-AE", { minimumFractionDigits: 2 })}`
                  : "—"
              }
              icon={TrendingUp}
              description="Average Order Value últimos 30 días"
            />
            <KpiCard
              title="Pedidos bloqueados (crédito)"
              value={kpis?.open_credit_holds ?? 0}
              icon={AlertTriangle}
              variant={kpis && kpis.open_credit_holds > 0 ? "danger" : "default"}
              description="SOs en estado on_credit_hold"
            />
            <KpiCard
              title="RMAs abiertos"
              value={kpis?.rma_open_count ?? 0}
              icon={Package}
              variant={kpis && kpis.rma_open_count > 0 ? "warning" : "default"}
              description="Devoluciones pendientes de procesar"
            />
          </>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Backorders table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Líneas en Backorder</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SO#</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Disponible est.</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {backordersLoading && (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                )}
                {!backordersLoading && (!backorders || backorders.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-muted-foreground text-sm">
                      Sin backorders
                    </TableCell>
                  </TableRow>
                )}
                {(backorders ?? []).map((bo) => (
                  <TableRow key={bo.so_line_id}>
                    <TableCell className="font-mono text-xs">
                      <Link href={`/ventas/pedidos/${bo.so_line_id}`} className="text-primary hover:underline">
                        {bo.so_number}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs">{bo.product_sku}</TableCell>
                    <TableCell className="text-xs">{bo.qty}</TableCell>
                    <TableCell className="text-xs">
                      {bo.first_available_date
                        ? new Date(bo.first_available_date).toLocaleDateString("es-AE")
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Recent SOs table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Pedidos Recientes</CardTitle>
            <Link href="/ventas/pedidos" className="text-xs text-primary hover:underline">
              Ver todos
            </Link>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SO#</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Importe</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sosLoading && (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                )}
                {!sosLoading && (recentSOs?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-muted-foreground text-sm">
                      Sin pedidos
                    </TableCell>
                  </TableRow>
                )}
                {(recentSOs?.items ?? []).map((so: SalesOrderRead) => {
                  const meta = STATUS_META[so.status] ?? { label: so.status, variant: "outline" };
                  return (
                    <TableRow key={so.id}>
                      <TableCell className="font-mono text-xs font-semibold">
                        <Link
                          href={`/ventas/pedidos/${so.id}`}
                          className="text-primary hover:underline"
                        >
                          {so.so_number}
                        </Link>
                      </TableCell>
                      <TableCell className="text-xs">{so.customer_id}</TableCell>
                      <TableCell>
                        <Badge variant={meta.variant as never}>{meta.label}</Badge>
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {so.total_amount
                          ? `${so.currency ?? "AED"} ${parseFloat(so.total_amount).toLocaleString("es-AE", { minimumFractionDigits: 2 })}`
                          : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
