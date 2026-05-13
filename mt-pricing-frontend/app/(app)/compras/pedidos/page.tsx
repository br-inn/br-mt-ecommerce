"use client";

import * as React from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
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
import { POForm } from "@/components/compras/po-form";
import {
  purchaseOrdersApi,
  type POStatus,
  type PurchaseOrderRead,
} from "@/lib/api/endpoints/purchase_orders";

const STATUS_META: Record<POStatus, { label: string; variant: string }> = {
  draft: { label: "Borrador", variant: "secondary" },
  confirmed: { label: "Confirmado", variant: "default" },
  partial: { label: "Parcial", variant: "warning" },
  received: { label: "Recibido", variant: "success" },
  cancelled: { label: "Cancelado", variant: "destructive" },
};

const STATUS_TABS: Array<{ value: POStatus | ""; label: string }> = [
  { value: "", label: "Todos" },
  { value: "draft", label: "Borrador" },
  { value: "confirmed", label: "Confirmado" },
  { value: "partial", label: "Parcial" },
  { value: "received", label: "Recibido" },
  { value: "cancelled", label: "Cancelado" },
];

export default function PurchaseOrdersPage() {
  const [statusFilter, setStatusFilter] = React.useState<POStatus | "">("");
  const [search, setSearch] = React.useState("");
  const [cursor, setCursor] = React.useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const filters = React.useMemo(
    () => ({
      status: (statusFilter || undefined) as POStatus | undefined,
      q: search || undefined,
      cursor: cursor ?? undefined,
      limit: 50,
    }),
    [statusFilter, search, cursor],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["purchase-orders", filters],
    queryFn: () => purchaseOrdersApi.list(filters),
  });

  function handleTabChange(value: string) {
    setStatusFilter(value as POStatus | "");
    setCursor(null);
  }

  function handleSearchChange(e: React.ChangeEvent<HTMLInputElement>) {
    setSearch(e.target.value);
    setCursor(null);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pedidos de compra</h1>
          <p className="text-sm text-muted-foreground">
            Gestión de Purchase Orders — flujo draft → confirmed → received
          </p>
        </div>
        <Button onClick={() => setSheetOpen(true)}>
          <Plus className="mr-2 size-4" />
          Nuevo pedido
        </Button>
      </header>

      <div className="flex flex-wrap items-end gap-4">
        <Tabs value={statusFilter} onValueChange={handleTabChange}>
          <TabsList>
            {STATUS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-2">
          <Input
            value={search}
            onChange={handleSearchChange}
            placeholder="Buscar por PO#"
            className="w-48"
          />
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            Actualizar
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>PO#</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={6} className="text-destructive">
                    Error al cargar los pedidos
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && (data?.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground">
                    No hay pedidos
                  </TableCell>
                </TableRow>
              )}
              {(data?.items ?? []).map((po: PurchaseOrderRead) => {
                const meta = STATUS_META[po.status] ?? {
                  label: po.status,
                  variant: "outline",
                };
                return (
                  <TableRow key={po.id}>
                    <TableCell className="font-mono text-xs font-semibold">
                      <Link
                        href={`/compras/pedidos/${po.id}`}
                        className="text-primary hover:underline"
                      >
                        {po.po_number}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs">
                      {po.supplier_code ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={meta.variant as never}>{meta.label}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{po.currency ?? "—"}</TableCell>
                    <TableCell className="text-xs">
                      {new Date(po.created_at).toLocaleDateString("es-AE")}
                    </TableCell>
                    <TableCell>
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/compras/pedidos/${po.id}`}>Ver</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {(data?.cursor?.next || cursor) && (
            <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
              {cursor && (
                <Button variant="ghost" size="sm" onClick={() => setCursor(null)}>
                  Primera página
                </Button>
              )}
              {data?.cursor?.next && (
                <Button
                  variant="outline"
                  size="sm"
                  className="ml-auto"
                  onClick={() => setCursor(data.cursor.next)}
                >
                  Siguiente página
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <POForm
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onCreated={() => refetch()}
      />
    </div>
  );
}
