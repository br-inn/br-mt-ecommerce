"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowRight, Loader2, Plus, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { GRForm } from "@/components/compras/gr-form";
import {
  goodsReceiptsApi,
  type GRStatus,
  type GoodsReceiptRead,
} from "@/lib/api/endpoints/goods_receipts";

// ---------------------------------------------------------------------------
// Status meta
// ---------------------------------------------------------------------------

const STATUS_META: Record<GRStatus, { label: string; variant: string }> = {
  pending: { label: "Pendiente", variant: "warning" },
  processed: { label: "Procesado", variant: "success" },
  error: { label: "Error", variant: "destructive" },
};

type TabValue = "all" | GRStatus;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncateId(id: string) {
  return id.slice(0, 8).toUpperCase();
}

function MapArrow({
  before,
  after,
}: {
  before: string | null;
  after: string | null;
}) {
  if (!before && !after) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="flex items-center gap-1 font-mono text-xs">
      <span className="text-muted-foreground">{before ?? "—"}</span>
      <ArrowRight className="size-3 text-muted-foreground" />
      <span className={after ? "font-semibold text-green-700 dark:text-green-400" : ""}>
        {after ?? "—"}
      </span>
    </span>
  );
}

function StatusBadge({ status }: { status: GRStatus }) {
  const meta = STATUS_META[status] ?? { label: status, variant: "outline" };
  return (
    <span className="inline-flex items-center gap-1.5">
      {status === "pending" && (
        <Loader2 className="size-3 animate-spin text-amber-500" />
      )}
      <Badge variant={meta.variant as never}>{meta.label}</Badge>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Row with retry button
// ---------------------------------------------------------------------------

function GRRow({
  gr,
  onRetry,
}: {
  gr: GoodsReceiptRead;
  onRetry: (id: string) => void;
}) {
  const pol = gr.po_line;
  return (
    <TableRow>
      <TableCell className="font-mono text-xs font-semibold text-muted-foreground">
        GR-{truncateId(gr.id)}
      </TableCell>
      <TableCell className="font-mono text-xs">{pol.sku}</TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">
        {pol.po_id.slice(0, 8).toUpperCase()}
      </TableCell>
      <TableCell className="text-right font-mono text-xs">
        {gr.qty_received}
      </TableCell>
      <TableCell>
        <MapArrow before={gr.map_before} after={gr.map_after} />
      </TableCell>
      <TableCell>
        <StatusBadge status={gr.status} />
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {new Date(gr.created_at).toLocaleDateString("es-AE")}
      </TableCell>
      <TableCell>
        {gr.status === "error" && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 gap-1 text-xs"
            onClick={() => onRetry(gr.id)}
          >
            <RotateCcw className="size-3" />
            Reintentar
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GoodsReceiptsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = React.useState<TabValue>("all");
  const [cursor, setCursor] = React.useState<string | undefined>(undefined);
  const [grFormOpen, setGrFormOpen] = React.useState(false);

  const statusFilter =
    activeTab === "all" ? undefined : activeTab;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["goods-receipts", activeTab, cursor],
    queryFn: () =>
      goodsReceiptsApi.list({
        status: statusFilter,
        cursor,
        limit: 50,
      }),
    staleTime: 10_000,
  });

  const { mutate: retryGR, isPending: retrying } = useMutation({
    mutationFn: (id: string) => goodsReceiptsApi.retry(id),
    onSuccess: (gr) => {
      toast.success(`GR ${truncateId(gr.id)} re-encolado`);
      queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : "Error al reintentar",
      );
    },
  });

  const handleTabChange = (value: string) => {
    setActiveTab(value as TabValue);
    setCursor(undefined);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Recepciones</h1>
          <p className="text-sm text-muted-foreground">
            Goods Receipts — registro de entrada de mercancía y cálculo MAP
          </p>
        </div>
        <Button size="sm" onClick={() => setGrFormOpen(true)}>
          <Plus className="mr-1.5 size-4" />
          Registrar recepción
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="pending">Pendiente</TabsTrigger>
          <TabsTrigger value="processed">Procesado</TabsTrigger>
          <TabsTrigger value="error">Error</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Table */}
      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">Error al cargar las recepciones</p>
      )}

      {!isLoading && !isError && (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>GR#</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>PO#</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead>MAP antes → después</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={8}
                      className="text-center text-sm text-muted-foreground py-8"
                    >
                      Sin recepciones
                    </TableCell>
                  </TableRow>
                )}
                {(data?.items ?? []).map((gr) => (
                  <GRRow
                    key={gr.id}
                    gr={gr}
                    onRetry={(id) => retryGR(id)}
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {(data?.cursor?.next || cursor) && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>Mostrando {data?.items.length ?? 0} registros</span>
              <div className="flex gap-2">
                {cursor && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCursor(undefined)}
                  >
                    Primera página
                  </Button>
                )}
                {data?.cursor?.next && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCursor(data.cursor.next ?? undefined)}
                  >
                    Siguiente
                  </Button>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* GR Form Sheet */}
      <GRForm
        open={grFormOpen}
        onOpenChange={setGrFormOpen}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
        }}
      />
    </div>
  );
}
