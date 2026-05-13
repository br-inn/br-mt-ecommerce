"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
  procurementApi,
  type PRCreatePayload,
  type PurchaseRequisitionRead,
} from "@/lib/api/endpoints/procurement";

const UOM_OPTIONS = ["UNIT", "KG", "MTR", "BOX", "PCE"] as const;

interface PRFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (pr: PurchaseRequisitionRead) => void;
}

function resetState() {
  return {
    qty: "",
    uom: "UNIT",
    product_id: "",
    required_date: "",
    cost_center_id: "",
    estimated_amount: "",
    notes: "",
  };
}

export function PRForm({ open, onOpenChange, onCreated }: PRFormProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState(resetState);

  function patch(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const { mutate: createPR, isPending } = useMutation({
    mutationFn: (payload: PRCreatePayload) =>
      procurementApi.createRequisition(payload),
    onSuccess: (pr) => {
      toast.success(`Requisición ${pr.pr_number} creada`);
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
      onCreated?.(pr);
      onOpenChange(false);
      setForm(resetState());
    },
    onError: () => {
      toast.error("Error al crear la requisición");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: PRCreatePayload = {
      qty: form.qty,
      uom: form.uom,
      product_id: form.product_id || null,
      required_date: form.required_date || null,
      cost_center_id: form.cost_center_id || null,
      estimated_amount: form.estimated_amount || null,
      notes: form.notes || null,
    };
    createPR(payload);
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full max-w-lg flex-col overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Nueva requisición de compra</SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-5 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="pr-qty">Cantidad *</Label>
              <Input
                id="pr-qty"
                type="number"
                min="0.0001"
                step="any"
                value={form.qty}
                onChange={(e) => patch("qty", e.target.value)}
                placeholder="1"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label>Unidad</Label>
              <Select value={form.uom} onValueChange={(v) => patch("uom", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UOM_OPTIONS.map((u) => (
                    <SelectItem key={u} value={u}>
                      {u}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="pr-product">ID Producto (UUID)</Label>
              <Input
                id="pr-product"
                value={form.product_id}
                onChange={(e) => patch("product_id", e.target.value)}
                placeholder="uuid del producto"
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="pr-date">Fecha requerida</Label>
              <Input
                id="pr-date"
                type="date"
                value={form.required_date}
                onChange={(e) => patch("required_date", e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="pr-amount">Importe estimado (AED)</Label>
              <Input
                id="pr-amount"
                type="number"
                min="0"
                step="any"
                value={form.estimated_amount}
                onChange={(e) => patch("estimated_amount", e.target.value)}
                placeholder="0.00"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="pr-cc">Centro de coste</Label>
              <Input
                id="pr-cc"
                value={form.cost_center_id}
                onChange={(e) => patch("cost_center_id", e.target.value)}
                placeholder="CC-001"
              />
            </div>

            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="pr-notes">Notas</Label>
              <Input
                id="pr-notes"
                value={form.notes}
                onChange={(e) => patch("notes", e.target.value)}
                placeholder="Justificación o detalles"
              />
            </div>
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
            <Button type="submit" disabled={isPending || !form.qty}>
              {isPending ? "Guardando..." : "Crear requisición"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
