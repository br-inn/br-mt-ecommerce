"use client";

import * as React from "react";
import { Plus, Pencil } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  procurementApi,
  type VendorConditionRead,
  type VendorConditionCreatePayload,
  type VendorConditionUpdatePayload,
} from "@/lib/api/endpoints/procurement";

function ConditionForm({
  open,
  onOpenChange,
  initial,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial: VendorConditionRead | null;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState<VendorConditionCreatePayload>({
    vendor_id: "",
    product_sku: "",
    price: "",
    uom: "UNIT",
    moq: 1,
    currency: "AED",
    is_active: true,
  });

  React.useEffect(() => {
    if (initial) {
      setForm({
        vendor_id: initial.vendor_id,
        product_sku: initial.product_sku,
        price: initial.price,
        uom: initial.uom,
        moq: initial.moq,
        lead_time_days: initial.lead_time_days ?? null,
        valid_from: initial.valid_from,
        valid_to: initial.valid_to ?? null,
        currency: initial.currency,
        is_active: initial.is_active,
      });
    }
  }, [initial]);

  function patch(field: string, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const { mutate: save, isPending } = useMutation({
    mutationFn: (): Promise<VendorConditionRead> => {
      if (initial?.id) {
        const update: VendorConditionUpdatePayload = {
          price: form.price,
          ...(form.uom !== undefined && { uom: form.uom }),
          ...(form.moq !== undefined && { moq: form.moq }),
          lead_time_days: form.lead_time_days ?? null,
          valid_to: form.valid_to ?? null,
          ...(form.currency !== undefined && { currency: form.currency }),
          ...(form.is_active !== undefined && { is_active: form.is_active }),
        };
        return procurementApi.updateVendorCondition(initial.id, update);
      }
      return procurementApi.createVendorCondition(form);
    },
    onSuccess: () => {
      toast.success(initial?.id ? "Condición actualizada" : "PIR creado");
      queryClient.invalidateQueries({ queryKey: ["vendor-conditions"] });
      onSaved();
      onOpenChange(false);
    },
    onError: () => toast.error("Error al guardar la condición"),
  });

  const isEdit = !!initial?.id;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full max-w-lg flex-col overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{isEdit ? "Editar PIR" : "Nuevo PIR (condición proveedor)"}</SheetTitle>
        </SheetHeader>
        <div className="flex flex-1 flex-col gap-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 space-y-1.5">
              <Label>Código proveedor *</Label>
              <Input
                value={form.vendor_id}
                onChange={(e) => patch("vendor_id", e.target.value)}
                placeholder="PROV-001"
                disabled={isEdit}
                required
              />
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label>SKU Producto *</Label>
              <Input
                value={form.product_sku}
                onChange={(e) => patch("product_sku", e.target.value)}
                placeholder="SKU del producto"
                className="font-mono text-xs"
                disabled={isEdit}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Precio *</Label>
              <Input
                type="number"
                min="0"
                step="any"
                value={form.price}
                onChange={(e) => patch("price", e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Moneda</Label>
              <Input
                value={form.currency ?? "AED"}
                maxLength={3}
                onChange={(e) => patch("currency", e.target.value.toUpperCase())}
              />
            </div>
            <div className="space-y-1.5">
              <Label>UoM</Label>
              <Input
                value={form.uom ?? "UNIT"}
                onChange={(e) => patch("uom", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>MOQ (cant. mínima)</Label>
              <Input
                type="number"
                min="1"
                value={form.moq ?? 1}
                onChange={(e) => patch("moq", parseInt(e.target.value, 10) || 1)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Lead time (días)</Label>
              <Input
                type="number"
                min="0"
                value={form.lead_time_days ?? ""}
                onChange={(e) =>
                  patch("lead_time_days", e.target.value ? parseInt(e.target.value, 10) : null)
                }
              />
            </div>
            {!isEdit && (
              <div className="space-y-1.5">
                <Label>Válido desde</Label>
                <Input
                  type="date"
                  value={form.valid_from ?? ""}
                  onChange={(e) => patch("valid_from", e.target.value || null)}
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Válido hasta</Label>
              <Input
                type="date"
                value={form.valid_to ?? ""}
                placeholder="Sin vencimiento"
                onChange={(e) => patch("valid_to", e.target.value || null)}
              />
            </div>
          </div>
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancelar
          </Button>
          <Button
            onClick={() => save()}
            disabled={isPending || !form.vendor_id || !form.product_sku || !form.price}
          >
            {isPending ? "Guardando..." : "Guardar"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export default function CondicionesProveedorPage() {
  const [filterVendor, setFilterVendor] = React.useState("");
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<VendorConditionRead | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["vendor-conditions", filterVendor],
    queryFn: () =>
      procurementApi.listVendorConditions({
        ...(filterVendor && { vendor_id: filterVendor }),
        active_only: false,
      }),
  });

  function openNew() {
    setEditing(null);
    setSheetOpen(true);
  }

  function openEdit(vc: VendorConditionRead) {
    setEditing(vc);
    setSheetOpen(true);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Condiciones de proveedor (PIR)
          </h1>
          <p className="text-sm text-muted-foreground">
            Purchasing Info Records — precios y condiciones por proveedor y producto
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="mr-2 size-4" />
          Nuevo PIR
        </Button>
      </header>

      <div className="flex items-center gap-3">
        <Input
          value={filterVendor}
          onChange={(e) => setFilterVendor(e.target.value)}
          placeholder="Filtrar por proveedor"
          className="w-56"
        />
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          Actualizar
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Proveedor</TableHead>
                <TableHead>Producto SKU</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>MOQ</TableHead>
                <TableHead>Lead time</TableHead>
                <TableHead>Válido desde</TableHead>
                <TableHead>Válido hasta</TableHead>
                <TableHead>Activo</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={10}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={10} className="text-destructive">
                    Error al cargar los PIRs
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && (data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} className="text-muted-foreground">
                    No hay PIRs registrados
                  </TableCell>
                </TableRow>
              )}
              {(data ?? []).map((vc) => (
                <TableRow key={vc.id}>
                  <TableCell className="text-xs font-mono">{vc.vendor_id}</TableCell>
                  <TableCell className="max-w-[120px] truncate font-mono text-xs">
                    {vc.product_sku}
                  </TableCell>
                  <TableCell className="text-xs font-semibold">{vc.price}</TableCell>
                  <TableCell className="text-xs">{vc.currency}</TableCell>
                  <TableCell className="text-xs">{vc.moq}</TableCell>
                  <TableCell className="text-xs">
                    {vc.lead_time_days != null ? `${vc.lead_time_days}d` : "—"}
                  </TableCell>
                  <TableCell className="text-xs">{vc.valid_from}</TableCell>
                  <TableCell className="text-xs">{vc.valid_to ?? "∞"}</TableCell>
                  <TableCell>
                    <Badge variant={vc.is_active ? "success" : "secondary"}>
                      {vc.is_active ? "Sí" : "No"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button size="sm" variant="ghost" onClick={() => openEdit(vc)}>
                      <Pencil className="size-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <ConditionForm
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        initial={editing}
        onSaved={() => refetch()}
      />
    </div>
  );
}
