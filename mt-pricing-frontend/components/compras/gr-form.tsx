"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { purchaseOrdersApi } from "@/lib/api/endpoints/purchase_orders";
import {
  goodsReceiptsApi,
  type GoodsReceiptRead,
} from "@/lib/api/endpoints/goods_receipts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GRFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pre-selecciona una línea concreta (desde el detalle de PO). */
  preselectedPoLineId?: string;
  /** ID del PO al que pertenece la línea pre-seleccionada. */
  preselectedPoId?: string;
  /** Callback cuando se crea y procesa el GR. */
  onCreated?: (gr: GoodsReceiptRead) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GRForm({
  open,
  onOpenChange,
  preselectedPoLineId,
  preselectedPoId,
  onCreated,
}: GRFormProps) {
  const queryClient = useQueryClient();

  // --- Form state ---
  const [selectedPoId, setSelectedPoId] = React.useState<string>(
    preselectedPoId ?? "",
  );
  const [selectedLineId, setSelectedLineId] = React.useState<string>(
    preselectedPoLineId ?? "",
  );
  const [qty, setQty] = React.useState<string>("");
  const [forceOverride, setForceOverride] = React.useState(false);
  const [showCostSection, setShowCostSection] = React.useState(false);
  const [actualUnitPrice, setActualUnitPrice] = React.useState<string>("");
  const [breakdown, setBreakdown] = React.useState({
    fob_eur: "",
    flete_eur: "",
    arancel_base_eur: "",
    arancel_pct: "",
  });
  const [notes, setNotes] = React.useState<string>("");

  // --- Reset when opened/closed ---
  React.useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedPoId(preselectedPoId ?? "");
      setSelectedLineId(preselectedPoLineId ?? "");
      setQty("");
      setForceOverride(false);
      setShowCostSection(false);
      setActualUnitPrice("");
      setBreakdown({ fob_eur: "", flete_eur: "", arancel_base_eur: "", arancel_pct: "" });
      setNotes("");
    }
  }, [open, preselectedPoId, preselectedPoLineId]);

  // --- POs confirmados/parciales ---
  const { data: posData } = useQuery({
    queryKey: ["purchase-orders-open"],
    queryFn: () =>
      purchaseOrdersApi.list({ status: "confirmed", limit: 200 }).then(async (r1) => {
        const r2 = await purchaseOrdersApi.list({ status: "partial", limit: 200 });
        return { items: [...r1.items, ...r2.items] };
      }),
    enabled: open,
    staleTime: 30_000,
  });

  // --- Detalle del PO seleccionado (para las líneas) ---
  const { data: poDetail } = useQuery({
    queryKey: ["purchase-order", selectedPoId],
    queryFn: () => purchaseOrdersApi.get(selectedPoId),
    enabled: Boolean(selectedPoId),
  });

  // Líneas pendientes (qty_received < qty_ordered)
  const pendingLines = React.useMemo(
    () =>
      (poDetail?.lines ?? []).filter(
        (l) => Number(l.qty_received) < Number(l.qty_ordered),
      ),
    [poDetail],
  );

  const selectedLine = React.useMemo(
    () => pendingLines.find((l) => l.id === selectedLineId) ?? null,
    [pendingLines, selectedLineId],
  );

  const pendingQty = selectedLine
    ? Number(selectedLine.qty_ordered) - Number(selectedLine.qty_received)
    : 0;

  const qtyNum = parseFloat(qty) || 0;
  const qtyExceeds = qtyNum > pendingQty && pendingQty > 0;

  // --- Mutation: crear GR ---
  const { mutate: createGR, isPending: creating } = useMutation({
    mutationFn: () =>
      goodsReceiptsApi.create({
        po_line_id: selectedLineId,
        qty_received: qty,
        actual_unit_price: actualUnitPrice || null,
        actual_breakdown: {
          fob_eur: breakdown.fob_eur || null,
          flete_eur: breakdown.flete_eur || null,
          arancel_base_eur: breakdown.arancel_base_eur || null,
          arancel_pct: breakdown.arancel_pct || null,
        },
        notes: notes || null,
        force: forceOverride,
      }),
    onSuccess: (gr) => {
      onOpenChange(false);
      queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", selectedPoId] });
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      // Polling automático
      startPolling(gr);
      onCreated?.(gr);
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Error al registrar la recepción");
    },
  });

  // --- Polling del estado ---
  const startPolling = React.useCallback(
    (gr: GoodsReceiptRead) => {
      const MAX_ITERATIONS = 20; // 20 × 3s = 60s
      let count = 0;

      const interval = setInterval(async () => {
        count++;
        try {
          const statusData = await goodsReceiptsApi.getStatus(gr.id);
          if (statusData.status === "processed") {
            clearInterval(interval);
            toast.success(
              `MAP: ${statusData.map_before ?? "—"} → ${statusData.map_after ?? "—"} AED. Precios en recálculo.`,
            );
            queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
          } else if (statusData.status === "error") {
            clearInterval(interval);
            toast.error(
              `Error al calcular MAP: ${statusData.error_summary ?? "error desconocido"}`,
            );
            queryClient.invalidateQueries({ queryKey: ["goods-receipts"] });
          } else if (count >= MAX_ITERATIONS) {
            clearInterval(interval);
          }
        } catch {
          clearInterval(interval);
        }
      }, 3000);
    },
    [queryClient],
  );

  const canSubmit =
    Boolean(selectedLineId) &&
    qtyNum > 0 &&
    !creating &&
    (!qtyExceeds || forceOverride);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-[560px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Registrar recepción</SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-5">
          {/* 1. Selector de PO */}
          {!preselectedPoId && (
            <div className="space-y-1.5">
              <Label htmlFor="po-select">Purchase Order</Label>
              <Select
                value={selectedPoId || undefined}
                onValueChange={(v) => {
                  setSelectedPoId(v);
                  setSelectedLineId("");
                }}
              >
                <SelectTrigger id="po-select">
                  <SelectValue placeholder="Selecciona un PO..." />
                </SelectTrigger>
                <SelectContent>
                  {(posData?.items ?? []).map((po) => (
                    <SelectItem key={po.id} value={po.id}>
                      {po.po_number}{" "}
                      <span className="text-muted-foreground text-xs ml-1">
                        ({po.status})
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* 2. Selector de línea */}
          {(selectedPoId || preselectedPoId) && !preselectedPoLineId && (
            <div className="space-y-1.5">
              <Label htmlFor="line-select">Línea</Label>
              <Select value={selectedLineId || undefined} onValueChange={setSelectedLineId}>
                <SelectTrigger id="line-select">
                  <SelectValue placeholder="Selecciona una línea..." />
                </SelectTrigger>
                <SelectContent>
                  {pendingLines.length === 0 && (
                    <SelectItem value="__none__" disabled>
                      Sin líneas pendientes
                    </SelectItem>
                  )}
                  {pendingLines.map((line) => (
                    <SelectItem key={line.id} value={line.id}>
                      {line.sku} — pendiente:{" "}
                      {Number(line.qty_ordered) - Number(line.qty_received)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Línea pre-seleccionada: mostrar info */}
          {preselectedPoLineId && selectedLine && (
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm space-y-0.5">
              <div>
                <span className="font-medium">SKU:</span> {selectedLine.sku}
              </div>
              <div>
                <span className="font-medium">Esquema:</span>{" "}
                {selectedLine.scheme_code}
              </div>
              <div>
                <span className="font-medium">Qty pendiente:</span>{" "}
                {pendingQty.toFixed(3)}
              </div>
            </div>
          )}

          {/* 3. Cantidad */}
          {selectedLineId && (
            <div className="space-y-1.5">
              <Label htmlFor="qty">
                Cantidad recibida{" "}
                {pendingQty > 0 && (
                  <span className="text-muted-foreground text-xs">
                    (máx. pendiente: {pendingQty.toFixed(3)})
                  </span>
                )}
              </Label>
              <Input
                id="qty"
                type="number"
                min="0.001"
                step="0.001"
                value={qty}
                onChange={(e) => {
                  setQty(e.target.value);
                  setForceOverride(false);
                }}
                placeholder="0.000"
                className={qtyExceeds && !forceOverride ? "border-destructive" : ""}
              />
              {qtyExceeds && (
                <div className="flex items-start gap-2 text-sm text-destructive">
                  <AlertTriangle className="size-4 mt-0.5 shrink-0" />
                  <span>
                    La cantidad supera la pendiente ({pendingQty.toFixed(3)}).
                  </span>
                </div>
              )}
              {qtyExceeds && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="force"
                    checked={forceOverride}
                    onCheckedChange={(v) => setForceOverride(Boolean(v))}
                  />
                  <Label htmlFor="force" className="text-sm font-normal cursor-pointer">
                    Recibir igualmente (override)
                  </Label>
                </div>
              )}
            </div>
          )}

          {/* 4. Sección "Coste real" colapsable */}
          {selectedLineId && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setShowCostSection((v) => !v)}
                className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {showCostSection ? (
                  <ChevronUp className="size-4" />
                ) : (
                  <ChevronDown className="size-4" />
                )}
                Coste real (opcional)
              </button>
              {showCostSection && (
                <div className="rounded-md border p-4 space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="actual-price">Precio factura (AED)</Label>
                    <Input
                      id="actual-price"
                      type="number"
                      min="0"
                      step="0.0001"
                      value={actualUnitPrice}
                      onChange={(e) => setActualUnitPrice(e.target.value)}
                      placeholder="0.0000"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="fob-eur">FOB (EUR)</Label>
                      <Input
                        id="fob-eur"
                        type="number"
                        min="0"
                        step="0.01"
                        value={breakdown.fob_eur}
                        onChange={(e) =>
                          setBreakdown((b) => ({ ...b, fob_eur: e.target.value }))
                        }
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="flete-eur">Flete (EUR)</Label>
                      <Input
                        id="flete-eur"
                        type="number"
                        min="0"
                        step="0.01"
                        value={breakdown.flete_eur}
                        onChange={(e) =>
                          setBreakdown((b) => ({ ...b, flete_eur: e.target.value }))
                        }
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="arancel-base">Arancel base (EUR)</Label>
                      <Input
                        id="arancel-base"
                        type="number"
                        min="0"
                        step="0.01"
                        value={breakdown.arancel_base_eur}
                        onChange={(e) =>
                          setBreakdown((b) => ({
                            ...b,
                            arancel_base_eur: e.target.value,
                          }))
                        }
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="arancel-pct">Arancel (%)</Label>
                      <Input
                        id="arancel-pct"
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={breakdown.arancel_pct}
                        onChange={(e) =>
                          setBreakdown((b) => ({
                            ...b,
                            arancel_pct: e.target.value,
                          }))
                        }
                        placeholder="0.00"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 5. Notas */}
          {selectedLineId && (
            <div className="space-y-1.5">
              <Label htmlFor="notes">Notas</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Observaciones opcionales..."
                rows={3}
              />
            </div>
          )}

          {/* Acciones */}
          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={creating}
            >
              Cancelar
            </Button>
            <Button
              disabled={!canSubmit}
              onClick={() => createGR()}
            >
              {creating ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Registrando...
                </>
              ) : (
                "Registrar recepción"
              )}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
