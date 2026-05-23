"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, Clock, Ban, Play } from "lucide-react";

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
import { vendorInvoicesApi, type VendorInvoiceStatus } from "@/lib/api/endpoints/procurement";

// ---------------------------------------------------------------------------
// Status metadata
// ---------------------------------------------------------------------------

const STATUS_META: Record<VendorInvoiceStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "warning" | "success"; icon: React.ReactNode }> = {
  pending: { label: "Pendiente", variant: "secondary", icon: <Clock className="h-3 w-3" /> },
  matched: { label: "Conciliado", variant: "success", icon: <CheckCircle className="h-3 w-3" /> },
  tolerance_ok: { label: "Tolerancia OK", variant: "default", icon: <CheckCircle className="h-3 w-3" /> },
  blocked: { label: "Bloqueado", variant: "destructive", icon: <Ban className="h-3 w-3" /> },
  approved: { label: "Aprobado", variant: "success", icon: <CheckCircle className="h-3 w-3" /> },
  paid: { label: "Pagado", variant: "outline", icon: <CheckCircle className="h-3 w-3" /> },
};

const STATUS_TABS: Array<{ value: VendorInvoiceStatus | ""; label: string }> = [
  { value: "", label: "Todas" },
  { value: "pending", label: "Pendientes" },
  { value: "blocked", label: "Bloqueadas" },
  { value: "matched", label: "Conciliadas" },
  { value: "approved", label: "Aprobadas" },
  { value: "paid", label: "Pagadas" },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function VendorInvoicesPage() {
  const [statusFilter, setStatusFilter] = React.useState<VendorInvoiceStatus | "">("");
  const queryClient = useQueryClient();

  const { data: invoices, isLoading, isError } = useQuery({
    queryKey: ["vendor-invoices", statusFilter],
    queryFn: () =>
      vendorInvoicesApi.list({ ...(statusFilter ? { status: statusFilter as VendorInvoiceStatus } : {}) }),
  });

  const matchMutation = useMutation({
    mutationFn: (invoiceId: string) => vendorInvoicesApi.match(invoiceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["vendor-invoices"] });
    },
  });

  if (isError) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-destructive">
          <AlertCircle className="mx-auto mb-2 h-8 w-8" />
          <p>Error al cargar facturas</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Facturas de Proveedor</h1>
          <p className="text-sm text-muted-foreground">
            Conciliación 3-way match: factura vs PO vs recepción
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        value={statusFilter}
        onValueChange={(v) => setStatusFilter(v as VendorInvoiceStatus | "")}
      >
        <TabsList>
          {STATUS_TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Número</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead className="text-right">Importe</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Bloqueo</TableHead>
                <TableHead className="w-32">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : (invoices ?? []).map((inv) => {
                    const meta = STATUS_META[inv.status] ?? STATUS_META.pending;
                    return (
                      <TableRow key={inv.id}>
                        <TableCell className="font-mono text-sm">
                          {inv.invoice_number}
                        </TableCell>
                        <TableCell>{inv.vendor_id}</TableCell>
                        <TableCell>
                          {new Date(inv.invoice_date).toLocaleDateString("es-AE")}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {Number(inv.total_amount).toLocaleString("es-AE", {
                            minimumFractionDigits: 2,
                          })}
                        </TableCell>
                        <TableCell>{inv.currency}</TableCell>
                        <TableCell>
                          <Badge variant={meta.variant} className="gap-1">
                            {meta.icon}
                            {meta.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {inv.payment_block && (
                            <Badge variant="destructive" className="gap-1">
                              <Ban className="h-3 w-3" />
                              Bloqueado
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {inv.status === "pending" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-1"
                              disabled={matchMutation.isPending}
                              onClick={() => matchMutation.mutate(inv.id)}
                            >
                              <Play className="h-3 w-3" />
                              Match
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
              {!isLoading && (invoices ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                    No hay facturas con el filtro seleccionado
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
