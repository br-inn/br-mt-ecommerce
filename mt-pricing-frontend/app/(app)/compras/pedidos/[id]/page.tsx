"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, PackageCheck } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
  purchaseOrdersApi,
  type POStatus,
} from "@/lib/api/endpoints/purchase_orders";
import { GRForm } from "@/components/compras/gr-form";

const STATUS_META: Record<POStatus, { label: string; variant: string }> = {
  draft: { label: "Borrador", variant: "secondary" },
  confirmed: { label: "Confirmado", variant: "default" },
  partial: { label: "Parcial", variant: "warning" },
  received: { label: "Recibido", variant: "success" },
  cancelled: { label: "Cancelado", variant: "destructive" },
};

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  // GR form state
  const [grFormOpen, setGrFormOpen] = React.useState(false);
  const [grPreLineId, setGrPreLineId] = React.useState<string | undefined>(undefined);

  function openReceiveForLine(lineId: string) {
    setGrPreLineId(lineId);
    setGrFormOpen(true);
  }

  const { data: po, isLoading, isError } = useQuery({
    queryKey: ["purchase-order", id],
    queryFn: () => purchaseOrdersApi.get(id),
    enabled: Boolean(id),
  });

  const { mutate: confirmPO, isPending: confirming } = useMutation({
    mutationFn: () => purchaseOrdersApi.confirm(id),
    onSuccess: (updated) => {
      toast.success(`PO ${updated.po_number} confirmado`);
      queryClient.invalidateQueries({ queryKey: ["purchase-order", id] });
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: () => toast.error("Error al confirmar el pedido"),
  });

  const { mutate: cancelPO, isPending: cancelling } = useMutation({
    mutationFn: () => purchaseOrdersApi.cancel(id),
    onSuccess: (updated) => {
      toast.success(`PO ${updated.po_number} cancelado`);
      queryClient.invalidateQueries({ queryKey: ["purchase-order", id] });
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: () => toast.error("Error al cancelar el pedido"),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !po) {
    return (
      <div className="space-y-4">
        <p className="text-destructive">Error al cargar el pedido</p>
        <Button variant="outline" asChild>
          <Link href="/compras/pedidos">
            <ArrowLeft className="mr-2 size-4" />
            Volver a pedidos
          </Link>
        </Button>
      </div>
    );
  }

  const meta = STATUS_META[po.status] ?? { label: po.status, variant: "outline" };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/compras/pedidos">
            <ArrowLeft className="size-4" />
          </Link>
        </Button>
        <div className="flex flex-1 flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight font-mono">
            {po.po_number}
          </h1>
          <Badge variant={meta.variant as never}>{meta.label}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {po.status === "draft" && (
            <Button
              size="sm"
              onClick={() => confirmPO()}
              disabled={confirming || cancelling}
            >
              {confirming ? "Confirmando..." : "Confirmar"}
            </Button>
          )}
          {po.status !== "cancelled" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => cancelPO()}
              disabled={confirming || cancelling}
            >
              {cancelling ? "Cancelando..." : "Cancelar"}
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Proveedor</dt>
              <dd className="text-sm">{po.supplier_code ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Tipo PO</dt>
              <dd className="font-mono text-xs">{po.po_type}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Moneda</dt>
              <dd className="text-sm">{po.currency ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Creado</dt>
              <dd className="text-sm">
                {new Date(po.created_at).toLocaleString("es-AE")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Confirmado</dt>
              <dd className="text-sm">
                {po.confirmed_at
                  ? new Date(po.confirmed_at).toLocaleString("es-AE")
                  : "—"}
              </dd>
            </div>
            {po.notes && (
              <div className="col-span-2 md:col-span-4">
                <dt className="text-xs font-medium text-muted-foreground">Notas</dt>
                <dd className="text-sm">{po.notes}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Líneas del pedido</h2>
        <Card>
          <CardContent className="pt-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Esquema</TableHead>
                  <TableHead className="text-right">Qty pedida</TableHead>
                  <TableHead className="text-right">Qty recibida</TableHead>
                  <TableHead className="text-right">P. Unitario</TableHead>
                  <TableHead>Estado recepción</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.lines.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-muted-foreground">
                      Sin líneas
                    </TableCell>
                  </TableRow>
                )}
                {po.lines.map((line) => {
                  const received = Number(line.qty_received);
                  const ordered = Number(line.qty_ordered);
                  const hasPending = received < ordered;
                  const receptionStatus =
                    received === 0
                      ? "Pendiente"
                      : received >= ordered
                        ? "Completo"
                        : "Parcial";
                  const canReceive =
                    hasPending &&
                    (po.status === "confirmed" || po.status === "partial");
                  const priceSource = line.price_source;
                  return (
                    <TableRow key={line.id}>
                      <TableCell className="font-mono text-xs">{line.sku}</TableCell>
                      <TableCell className="text-xs">{line.scheme_code}</TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {line.qty_ordered}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {line.qty_received}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        <span>{line.unit_price} {po.currency}</span>
                        {priceSource === "pir" && (
                          <Badge variant="outline" className="ml-1 text-[10px] px-1">
                            PIR
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {receptionStatus}
                      </TableCell>
                      <TableCell>
                        {canReceive && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 gap-1 text-xs"
                            onClick={() => openReceiveForLine(line.id)}
                          >
                            <PackageCheck className="size-3" />
                            Recibir
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">
          Recepciones{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({po.gr_count})
          </span>
        </h2>
        <Card>
          <CardContent className="pt-4">
            {po.gr_count === 0 ? (
              <p className="text-sm text-muted-foreground">
                No hay recepciones registradas para este pedido
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                {po.gr_count} recepción(es) — detalle disponible en la pantalla de Recepciones
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {/* GR Form pre-cargado con la línea */}
      <GRForm
        open={grFormOpen}
        onOpenChange={(v) => {
          setGrFormOpen(v);
          if (!v) setGrPreLineId(undefined);
        }}
        preselectedPoId={id}
        {...(grPreLineId !== undefined ? { preselectedPoLineId: grPreLineId } : {})}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ["purchase-order", id] });
          queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
        }}
      />
    </div>
  );
}
