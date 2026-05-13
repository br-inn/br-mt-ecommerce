"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetFooter,
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
import {
  purchaseOrdersApi,
  type POCreatePayload,
  type POLineCreatePayload,
  type PurchaseOrderRead,
} from "@/lib/api/endpoints/purchase_orders";

interface Supplier {
  code: string;
  name: string;
}

interface LineState extends POLineCreatePayload {
  _key: string;
  _showBreakdown: boolean;
}

interface POFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (po: PurchaseOrderRead) => void;
}

const CURRENCIES = ["AED", "EUR", "USD"] as const;
const PO_TYPES = ["STANDARD", "BLANKET", "CONTRACT", "SCHEDULING"] as const;

function newLine(): LineState {
  return {
    _key: crypto.randomUUID(),
    _showBreakdown: false,
    sku: "",
    scheme_code: "",
    qty_ordered: "",
    unit_price: "",
    landed_cost_breakdown: {
      fob_eur: "",
      flete_eur: "",
      arancel_base_eur: "",
      arancel_pct: "",
    },
  };
}

export function POForm({ open, onOpenChange, onCreated }: POFormProps) {
  const queryClient = useQueryClient();

  const [poNumber, setPoNumber] = React.useState("");
  const [supplierCode, setSupplierCode] = React.useState<string>("");
  const [currency, setCurrency] = React.useState<string>("AED");
  const [poType, setPoType] = React.useState<string>("STANDARD");
  const [notes, setNotes] = React.useState("");
  const [lines, setLines] = React.useState<LineState[]>([newLine()]);

  const { data: suppliersData } = useQuery<{ items: Supplier[] }>({
    queryKey: ["suppliers-list"],
    queryFn: () =>
      fetch("/api/v1/suppliers?limit=200", { cache: "no-store" }).then((r) =>
        r.json(),
      ),
    enabled: open,
  });
  const suppliers: Supplier[] = suppliersData?.items ?? [];

  const { mutate: createPO, isPending } = useMutation({
    mutationFn: (payload: POCreatePayload) => purchaseOrdersApi.create(payload),
    onSuccess: (po) => {
      toast.success(`PO ${po.po_number} creado como borrador`);
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      onCreated?.(po);
      onOpenChange(false);
      resetForm();
    },
    onError: () => {
      toast.error("Error al crear el pedido");
    },
  });

  function resetForm() {
    setPoNumber("");
    setSupplierCode("");
    setCurrency("AED");
    setPoType("STANDARD");
    setNotes("");
    setLines([newLine()]);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validLines = lines.filter((l) => l.sku && l.scheme_code && l.qty_ordered && l.unit_price);
    createPO({
      po_number: poNumber,
      supplier_code: supplierCode || null,
      currency: currency || null,
      po_type: poType,
      notes: notes || null,
      lines: validLines.map((l) => ({
        sku: l.sku,
        scheme_code: l.scheme_code,
        qty_ordered: l.qty_ordered,
        unit_price: l.unit_price,
        landed_cost_breakdown: l.landed_cost_breakdown,
      })),
    });
  }

  function updateLine(key: string, patch: Partial<LineState>) {
    setLines((prev) => prev.map((l) => (l._key === key ? { ...l, ...patch } : l)));
  }

  function updateBreakdown(key: string, field: string, value: string) {
    setLines((prev) =>
      prev.map((l) =>
        l._key === key
          ? {
              ...l,
              landed_cost_breakdown: { ...l.landed_cost_breakdown, [field]: value },
            }
          : l,
      ),
    );
  }

  function removeLine(key: string) {
    setLines((prev) => prev.filter((l) => l._key !== key));
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full max-w-2xl flex-col overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Nuevo pedido de compra</SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-6 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="po-number">Nº Pedido *</Label>
              <Input
                id="po-number"
                value={poNumber}
                onChange={(e) => setPoNumber(e.target.value)}
                placeholder="PO-2026-001"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label>Proveedor</Label>
              <Select value={supplierCode || undefined} onValueChange={setSupplierCode}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar proveedor" />
                </SelectTrigger>
                <SelectContent>
                  {suppliers.map((s) => (
                    <SelectItem key={s.code} value={s.code}>
                      {s.name || s.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Moneda</Label>
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Tipo PO</Label>
              <Select value={poType} onValueChange={setPoType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PO_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="po-notes">Notas</Label>
              <Input
                id="po-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Observaciones opcionales"
              />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Líneas</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setLines((prev) => [...prev, newLine()])}
              >
                <Plus className="mr-1.5 size-3.5" />
                Agregar línea
              </Button>
            </div>

            {lines.map((line, idx) => (
              <div key={line._key} className="rounded-md border p-3 space-y-3">
                <div className="grid grid-cols-[1fr_1fr_auto_auto_auto] gap-2 items-end">
                  <div className="space-y-1">
                    <Label className="text-xs">SKU</Label>
                    <Input
                      value={line.sku}
                      onChange={(e) => updateLine(line._key, { sku: e.target.value })}
                      placeholder="MT-V-038"
                      className="text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Esquema</Label>
                    <Input
                      value={line.scheme_code}
                      onChange={(e) => updateLine(line._key, { scheme_code: e.target.value })}
                      placeholder="FBA"
                      className="text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Cant.</Label>
                    <Input
                      type="number"
                      min="0.001"
                      step="any"
                      value={line.qty_ordered}
                      onChange={(e) => updateLine(line._key, { qty_ordered: e.target.value })}
                      className="w-24 text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">P. Unit.</Label>
                    <Input
                      type="number"
                      min="0"
                      step="any"
                      value={line.unit_price}
                      onChange={(e) => updateLine(line._key, { unit_price: e.target.value })}
                      className="w-28 text-xs"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeLine(line._key)}
                    disabled={lines.length === 1}
                    className="self-end"
                  >
                    <Trash2 className="size-3.5 text-destructive" />
                  </Button>
                </div>

                <button
                  type="button"
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => updateLine(line._key, { _showBreakdown: !line._showBreakdown })}
                >
                  {line._showBreakdown ? (
                    <ChevronDown className="size-3" />
                  ) : (
                    <ChevronRight className="size-3" />
                  )}
                  Costes de aterrizaje (indicativo)
                </button>

                {line._showBreakdown && (
                  <div className="grid grid-cols-4 gap-2 pl-4">
                    {(
                      [
                        ["fob_eur", "FOB EUR"],
                        ["flete_eur", "Flete EUR"],
                        ["arancel_base_eur", "Arancel base EUR"],
                        ["arancel_pct", "Arancel %"],
                      ] as const
                    ).map(([field, label]) => (
                      <div key={field} className="space-y-1">
                        <Label className="text-xs">{label}</Label>
                        <Input
                          type="number"
                          min="0"
                          step="any"
                          value={
                            (line.landed_cost_breakdown?.[field] as string | undefined) ?? ""
                          }
                          onChange={(e) => updateBreakdown(line._key, field, e.target.value)}
                          className="text-xs"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <SheetFooter className="mt-auto">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isPending || !poNumber}>
              {isPending ? "Guardando..." : "Guardar borrador"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
