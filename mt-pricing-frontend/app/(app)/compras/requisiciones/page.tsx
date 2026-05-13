"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PRForm } from "@/components/compras/pr-form";
import {
  procurementApi,
  type PRStatus,
  type PurchaseRequisitionRead,
} from "@/lib/api/endpoints/procurement";

const STATUS_META: Record<PRStatus, { label: string; variant: string }> = {
  draft: { label: "Borrador", variant: "secondary" },
  pending_approval: { label: "Pendiente aprobación", variant: "warning" },
  approved: { label: "Aprobada", variant: "success" },
  rejected: { label: "Rechazada", variant: "destructive" },
  cancelled: { label: "Cancelada", variant: "outline" },
  converted_to_po: { label: "Convertida a PO", variant: "default" },
};

const STATUS_TABS: Array<{ value: PRStatus | ""; label: string }> = [
  { value: "", label: "Todas" },
  { value: "draft", label: "Borrador" },
  { value: "pending_approval", label: "Pendiente" },
  { value: "approved", label: "Aprobadas" },
  { value: "rejected", label: "Rechazadas" },
];

export default function RequisicionesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = React.useState<PRStatus | "">("");
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["purchase-requisitions", statusFilter],
    queryFn: () =>
      procurementApi.listRequisitions({
        status: statusFilter || undefined,
        limit: 50,
      }),
  });

  const { mutate: submitPR } = useMutation({
    mutationFn: (id: string) => procurementApi.submitRequisition(id),
    onSuccess: (pr) => {
      const meta = STATUS_META[pr.status];
      toast.success(`PR ${pr.pr_number} → ${meta?.label ?? pr.status}`);
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
    },
    onError: () => toast.error("Error al enviar la requisición"),
  });

  const { mutate: cancelPR } = useMutation({
    mutationFn: (id: string) => procurementApi.cancelRequisition(id),
    onSuccess: () => {
      toast.success("Requisición cancelada");
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
    },
    onError: () => toast.error("Error al cancelar"),
  });

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Requisiciones de compra
          </h1>
          <p className="text-sm text-muted-foreground">
            Solicitudes internas — flujo draft → aprobación → PO
          </p>
        </div>
        <Button onClick={() => setSheetOpen(true)}>
          <Plus className="mr-2 size-4" />
          Nueva requisición
        </Button>
      </header>

      <div className="flex flex-wrap items-end gap-4">
        <Tabs value={statusFilter} onValueChange={(v) => setStatusFilter(v as PRStatus | "")}>
          <TabsList>
            {STATUS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          Actualizar
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>PR#</TableHead>
                <TableHead>Cantidad</TableHead>
                <TableHead>UoM</TableHead>
                <TableHead>Importe est.</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="text-destructive">
                    Error al cargar las requisiciones
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && (data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-muted-foreground">
                    No hay requisiciones
                  </TableCell>
                </TableRow>
              )}
              {(data ?? []).map((pr: PurchaseRequisitionRead) => {
                const meta = STATUS_META[pr.status] ?? {
                  label: pr.status,
                  variant: "outline",
                };
                return (
                  <TableRow key={pr.id}>
                    <TableCell className="font-mono text-xs font-semibold">
                      {pr.pr_number}
                    </TableCell>
                    <TableCell className="text-xs">{pr.qty}</TableCell>
                    <TableCell className="text-xs">{pr.uom}</TableCell>
                    <TableCell className="text-xs">
                      {pr.estimated_amount
                        ? `${pr.estimated_amount} AED`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={meta.variant as never}>{meta.label}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {new Date(pr.created_at).toLocaleDateString("es-AE")}
                    </TableCell>
                    <TableCell className="flex gap-1">
                      {pr.status === "draft" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => submitPR(pr.id)}
                        >
                          Enviar
                        </Button>
                      )}
                      {pr.status !== "converted_to_po" &&
                        pr.status !== "cancelled" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => cancelPR(pr.id)}
                          >
                            Cancelar
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

      <PRForm
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onCreated={() => refetch()}
      />
    </div>
  );
}
