"use client";

import { useState } from "react";
import { Ruler, ArrowRight, Plus, Trash2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { productsApi } from "@/lib/api/endpoints/products";
import { useProduct } from "@/lib/hooks/products/use-product";
import type { ProductUomConversion } from "@/lib/api/endpoints/products";

// ---- Dialog para crear conversión UoM -----------------------------------

interface UomFormState {
  uom_from: string;
  uom_to: string;
  factor: string;
}

const EMPTY_UOM_FORM: UomFormState = { uom_from: "", uom_to: "", factor: "" };

function AgregarConversionDialog({
  sku,
  onSuccess,
}: {
  sku: string;
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<UomFormState>(EMPTY_UOM_FORM);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      productsApi.createUomConversion(sku, {
        uom_from: form.uom_from.trim().toUpperCase(),
        uom_to: form.uom_to.trim().toUpperCase(),
        factor: Number(form.factor),
      }),
    onSuccess: () => {
      setOpen(false);
      setForm(EMPTY_UOM_FORM);
      setError(null);
      onSuccess();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Error al crear la conversión.");
    },
  });

  const handleOpenChange = (v: boolean) => {
    if (!v) {
      setForm(EMPTY_UOM_FORM);
      setError(null);
    }
    setOpen(v);
  };

  const handleSubmit = () => {
    if (!form.uom_from.trim()) { setError("UoM origen es obligatoria."); return; }
    if (!form.uom_to.trim()) { setError("UoM destino es obligatoria."); return; }
    const f = Number(form.factor);
    if (!form.factor || isNaN(f) || f <= 0) { setError("El factor debe ser un número positivo."); return; }
    setError(null);
    createMutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="h-4 w-4" /> Agregar
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Agregar conversión de unidad</DialogTitle>
          <DialogDescription>
            Define la equivalencia entre dos unidades de medida para este producto.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="uom_from">UoM origen</Label>
            <Input
              id="uom_from"
              placeholder="BOX, PALLET, PACK…"
              value={form.uom_from}
              onChange={(e) => setForm((f) => ({ ...f, uom_from: e.target.value }))}
              className="uppercase"
              maxLength={20}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="uom_to">UoM destino</Label>
            <Input
              id="uom_to"
              placeholder="UNIT, EA, KG…"
              value={form.uom_to}
              onChange={(e) => setForm((f) => ({ ...f, uom_to: e.target.value }))}
              className="uppercase"
              maxLength={20}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="factor">Factor de conversión</Label>
            <Input
              id="factor"
              type="number"
              min="0.0001"
              step="any"
              placeholder="12"
              value={form.factor}
              onChange={(e) => setForm((f) => ({ ...f, factor: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">
              Ej: 12 significa que 1 {form.uom_from || "BOX"} = 12 {form.uom_to || "UNIT"}.
            </p>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>
        <DialogFooter>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? "Guardando…" : "Guardar conversión"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  sku: string;
}

export function UnidadesClient({ sku }: Props) {
  const queryClient = useQueryClient();
  const { data: product, isLoading: loadingProduct } = useProduct(sku);

  const { data: conversions, isLoading: loadingConv } = useQuery({
    queryKey: ["product-uom-conversions", sku],
    queryFn: () => productsApi.listUomConversions(sku),
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: ({ uomFrom, uomTo }: { uomFrom: string; uomTo: string }) =>
      productsApi.deleteUomConversion(sku, uomFrom, uomTo),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["product-uom-conversions", sku] });
    },
  });

  const isLoading = loadingProduct || loadingConv;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-28 w-full rounded-lg" />
        <Skeleton className="h-48 w-full rounded-lg" />
      </div>
    );
  }

  const baseUom = (product as { base_uom?: string | null } | undefined)?.base_uom ?? "UNIT";

  return (
    <div className="flex flex-col gap-4">
      {/* Card de UoM base — inspirado en SAP MM base unit of measure */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ruler className="h-5 w-5 text-muted-foreground" />
            Unidad de Medida Base
          </CardTitle>
          <CardDescription>
            Todas las transacciones (stock, compras, ventas) se calculan en esta UoM.
            Las conversiones definen factores para empaques o unidades alternativas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Badge variant="default" className="px-4 py-1.5 text-base font-bold">
              {baseUom}
            </Badge>
            <span className="text-sm text-muted-foreground">UoM canónica del producto</span>
          </div>
        </CardContent>
      </Card>

      {/* Tabla de conversiones — SAP MM alternate UoM */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>Conversiones de Unidades</CardTitle>
            <CardDescription>
              Equivalencias entre unidades alternativas y la UoM base.
              Ej: 1 BOX = 12 {baseUom}.
            </CardDescription>
          </div>
          <RbacGuard permissions={["products:write"]}>
            <AgregarConversionDialog
              sku={sku}
              onSuccess={() =>
                void queryClient.invalidateQueries({
                  queryKey: ["product-uom-conversions", sku],
                })
              }
            />
          </RbacGuard>
        </CardHeader>

        <CardContent>
          {!conversions || conversions.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
              <Ruler className="h-8 w-8 opacity-30" />
              <p className="text-sm">No hay conversiones definidas para este producto.</p>
              <p className="text-xs">
                Las conversiones permiten comprar en BOX y registrar stock en {baseUom}.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>De</TableHead>
                  <TableHead></TableHead>
                  <TableHead>A</TableHead>
                  <TableHead className="text-right">Factor</TableHead>
                  <TableHead>Dirección</TableHead>
                  <TableHead>Estado</TableHead>
                  <RbacGuard permissions={["products:write"]}>
                    <TableHead className="text-right">Acciones</TableHead>
                  </RbacGuard>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversions.map((conv: ProductUomConversion) => (
                  <TableRow key={conv.id}>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">
                        {conv.uom_from}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono">
                        {conv.uom_to}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono font-semibold">
                      × {conv.factor}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {conv.direction ?? "—"}
                    </TableCell>
                    <TableCell>
                      {conv.is_active ? (
                        <span className="text-sm text-green-600 font-medium">Activa</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">Inactiva</span>
                      )}
                    </TableCell>
                    <RbacGuard permissions={["products:write"]}>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() =>
                            deleteMutation.mutate({
                              uomFrom: conv.uom_from,
                              uomTo: conv.uom_to,
                            })
                          }
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </RbacGuard>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
