"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart2, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { rfqApi, type RfqStatus } from "@/lib/api/endpoints/procurement";

// ---------------------------------------------------------------------------
// Status metadata
// ---------------------------------------------------------------------------

const STATUS_META: Record<RfqStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "warning" | "success" }> = {
  draft: { label: "Borrador", variant: "secondary" },
  sent: { label: "Enviado", variant: "default" },
  responses_received: { label: "Respuestas recibidas", variant: "warning" },
  awarded: { label: "Adjudicado", variant: "success" },
  cancelled: { label: "Cancelado", variant: "destructive" },
};

// ---------------------------------------------------------------------------
// Comparison Modal
// ---------------------------------------------------------------------------

function ComparisonModal({
  rfqId,
  open,
  onClose,
}: {
  rfqId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["rfq-comparison", rfqId],
    queryFn: () => rfqApi.comparison(rfqId!),
    enabled: open && rfqId != null,
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            Comparativa de respuestas — {data?.rfq_number ?? rfqId}
          </DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="space-y-2 py-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Proveedor</TableHead>
                <TableHead className="text-right">Precio unitario</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead className="text-right">Plazo (días)</TableHead>
                <TableHead className="text-right">Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.items ?? []).map((item, idx) => (
                <TableRow key={item.vendor_id} className={idx === 0 ? "bg-green-50 dark:bg-green-950/20" : ""}>
                  <TableCell className="font-medium">{item.vendor_id}</TableCell>
                  <TableCell className="text-right font-mono">
                    {item.unit_price != null
                      ? Number(item.unit_price).toLocaleString("es-AE", { minimumFractionDigits: 4 })
                      : "—"}
                  </TableCell>
                  <TableCell>{item.currency}</TableCell>
                  <TableCell className="text-right">
                    {item.lead_time_days ?? "—"}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {item.score != null ? item.score.toFixed(4) : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {(data?.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                    No hay respuestas registradas para este RFQ
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
        <p className="text-xs text-muted-foreground">
          Score = 0.6 × (1 / precio_norm) + 0.4 × (1 / plazo_norm). Mayor es mejor.
          El proveedor en verde tiene el mayor score.
        </p>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function RfqPage() {
  const [selectedRfqId, setSelectedRfqId] = React.useState<string | null>(null);
  const [comparisonOpen, setComparisonOpen] = React.useState(false);

  const { data: rfqs, isLoading } = useQuery({
    queryKey: ["rfqs"],
    queryFn: () => rfqApi.list(),
  });

  const handleViewComparison = (rfqId: string) => {
    setSelectedRfqId(rfqId);
    setComparisonOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Solicitudes de Cotización (RFQ)
          </h1>
          <p className="text-sm text-muted-foreground">
            Gestión de RFQs y comparativa de respuestas de proveedores
          </p>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Número RFQ</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Fecha límite</TableHead>
                <TableHead>Fecha creación</TableHead>
                <TableHead>PR vinculada</TableHead>
                <TableHead className="w-36">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 6 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : (rfqs ?? []).map((rfq) => {
                    const meta = STATUS_META[rfq.status] ?? STATUS_META.draft;
                    const isExpired =
                      rfq.deadline != null &&
                      new Date(rfq.deadline) < new Date() &&
                      rfq.status !== "awarded" &&
                      rfq.status !== "cancelled";
                    return (
                      <TableRow key={rfq.id}>
                        <TableCell className="font-mono text-sm">
                          {rfq.rfq_number}
                        </TableCell>
                        <TableCell>
                          <Badge variant={meta.variant}>{meta.label}</Badge>
                        </TableCell>
                        <TableCell>
                          {rfq.deadline ? (
                            <span className={isExpired ? "text-destructive" : ""}>
                              {isExpired && <Clock className="mr-1 inline h-3 w-3" />}
                              {new Date(rfq.deadline).toLocaleDateString("es-AE")}
                            </span>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                        <TableCell>
                          {new Date(rfq.created_at).toLocaleDateString("es-AE")}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {rfq.pr_id ?? "—"}
                        </TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="gap-1"
                            onClick={() => handleViewComparison(rfq.id)}
                          >
                            <BarChart2 className="h-3 w-3" />
                            Comparativa
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
              {!isLoading && (rfqs ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    No hay RFQs creados
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Comparison Modal */}
      <ComparisonModal
        rfqId={selectedRfqId}
        open={comparisonOpen}
        onClose={() => setComparisonOpen(false)}
      />
    </div>
  );
}
