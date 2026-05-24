"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { salesApi, type SOStatus, type SalesOrderRead } from "@/lib/api/endpoints/sales";

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

const STATUS_TABS: Array<{ value: SOStatus | ""; label: string }> = [
  { value: "", label: "Todos" },
  { value: "draft", label: "Borrador" },
  { value: "confirmed", label: "Confirmado" },
  { value: "in_fulfillment", label: "En preparación" },
  { value: "partially_delivered", label: "Parcial" },
  { value: "delivered", label: "Entregado" },
  { value: "on_credit_hold", label: "Crédito bloqueado" },
  { value: "cancelled", label: "Cancelado" },
];

export default function VentasPedidosPage() {
  const [statusFilter, setStatusFilter] = React.useState<SOStatus | "">("");
  const [customerFilter, setCustomerFilter] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const LIMIT = 50;

  const filters = React.useMemo(
    () => ({
      ...(statusFilter ? { status: statusFilter as SOStatus } : {}),
      ...(customerFilter ? { customer_id: customerFilter } : {}),
      limit: LIMIT,
      offset,
    }),
    [statusFilter, customerFilter, offset],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["sales-orders", filters],
    queryFn: () => salesApi.listOrders(filters),
  });

  function handleTabChange(value: string) {
    setStatusFilter(value as SOStatus | "");
    setOffset(0);
  }

  function handleCustomerChange(e: React.ChangeEvent<HTMLInputElement>) {
    setCustomerFilter(e.target.value);
    setOffset(0);
  }

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0;
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pedidos de venta</h1>
          <p className="text-sm text-muted-foreground">
            Gestión de Sales Orders — flujo O2C
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/ventas/dashboard">
            <Button variant="outline" size="sm">Dashboard</Button>
          </Link>
          <Button onClick={() => refetch()} variant="ghost" size="sm">
            Actualizar
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-end gap-4">
        <Tabs value={statusFilter} onValueChange={handleTabChange}>
          <TabsList className="flex-wrap h-auto">
            {STATUS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Input
          value={customerFilter}
          onChange={handleCustomerChange}
          placeholder="Filtrar por cliente ID"
          className="w-48"
        />
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SO#</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Importe total</TableHead>
                <TableHead>F. entrega</TableHead>
                <TableHead>Creado</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={9}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={9} className="text-destructive">
                    Error al cargar los pedidos de venta
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && (data?.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-muted-foreground">
                    No hay pedidos
                  </TableCell>
                </TableRow>
              )}
              {(data?.items ?? []).map((so: SalesOrderRead) => {
                const meta = STATUS_META[so.status] ?? {
                  label: so.status,
                  variant: "outline",
                };
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
                    <TableCell className="text-xs">{so.order_type}</TableCell>
                    <TableCell>
                      <Badge variant={meta.variant as never}>{meta.label}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{so.currency ?? "AED"}</TableCell>
                    <TableCell className="text-xs font-mono">
                      {so.total_amount
                        ? parseFloat(so.total_amount).toLocaleString("es-AE", {
                            minimumFractionDigits: 2,
                          })
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {so.requested_delivery_date
                        ? new Date(so.requested_delivery_date).toLocaleDateString("es-AE")
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {new Date(so.created_at).toLocaleDateString("es-AE")}
                    </TableCell>
                    <TableCell>
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/ventas/pedidos/${so.id}`}>Ver</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Página {currentPage} de {totalPages} ({data?.total ?? 0} pedidos)
              </span>
              <div className="flex gap-2">
                {offset > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                  >
                    Anterior
                  </Button>
                )}
                {currentPage < totalPages && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOffset(offset + LIMIT)}
                  >
                    Siguiente
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
