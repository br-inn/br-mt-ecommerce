"use client";

import * as React from "react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { productsApi } from "@/lib/api/endpoints/products";
import { productKeys } from "@/lib/hooks/products/query-keys";
import { useProduct } from "@/lib/hooks/products/use-product";
import type {
  Product,
  ProductLifecycleStatus,
  DataQuality,
} from "@/lib/api/endpoints/products";

const LIFECYCLE_OPTIONS: { value: ProductLifecycleStatus; label: string }[] = [
  { value: "draft", label: "Borrador" },
  { value: "in_review", label: "En revisión" },
  { value: "active", label: "Activo" },
  { value: "deprecated", label: "Obsoleto" },
  { value: "replaced", label: "Reemplazado" },
  { value: "discontinued", label: "Descontinuado" },
];

const QUALITY_OPTIONS: { value: DataQuality; label: string }[] = [
  { value: "partial", label: "Parcial" },
  { value: "complete", label: "Completa" },
  { value: "blocked", label: "Bloqueada" },
];

interface Props {
  sku: string;
  /** Pasar cuando el producto ya está en caché (p.ej. desde el header del detalle).
   *  Si se omite, el drawer lo fetcha internamente por SKU. */
  product?: Product;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProductEditDrawer({ sku, product: productProp, open, onOpenChange }: Props) {
  const { data: fetchedProduct, isLoading: isProductLoading } = useProduct(sku);
  const product = productProp ?? fetchedProduct;

  const queryClient = useQueryClient();

  const [draft, setDraft] = React.useState({
    name_es: "" as string,
    name_ar: "" as string,
    brand: "",
    gtin: "",
    lifecycle_status: "active" as ProductLifecycleStatus,
    data_quality: "partial" as DataQuality,
  });

  // Sync draft when product changes
  React.useEffect(() => {
    if (!product) return;
    setDraft({
      name_es: (product.translations?.es?.name ?? "") as string,
      name_ar: (product.translations?.ar?.name ?? "") as string,
      brand: product.brand ?? "",
      gtin: product.gtin ?? "",
      lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
      data_quality: (product.data_quality ?? "partial") as DataQuality,
    });
  }, [product]);

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      productsApi.update(sku, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.detail(sku) });
      onOpenChange(false);
      toast.success("Producto actualizado");
    },
    onError: () => {
      toast.error("Error al guardar los cambios");
    },
  });

  const handleSave = () => {
    if (!product) return;
    const original = product;
    const payload: Record<string, unknown> = {
      lifecycle_status: draft.lifecycle_status,
      data_quality: draft.data_quality,
    };

    if (draft.brand !== (original.brand ?? "")) {
      payload.brand = draft.brand || null;
    }
    if (draft.gtin !== (original.gtin ?? "")) {
      payload.gtin = draft.gtin || null;
    }

    const originalNameEs = (original.translations?.es?.name ?? "") as string;
    const originalNameAr = (original.translations?.ar?.name ?? "") as string;
    const transPayload: Record<string, { name: string }> = {};
    if (draft.name_es !== originalNameEs && draft.name_es.trim()) {
      transPayload.es = { name: draft.name_es.trim() };
    }
    if (draft.name_ar !== originalNameAr && draft.name_ar.trim()) {
      transPayload.ar = { name: draft.name_ar.trim() };
    }
    if (Object.keys(transPayload).length > 0) {
      payload.translations = transPayload;
    }

    patchMutation.mutate(payload);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
        {!product && isProductLoading ? (
          <div className="flex h-40 items-center justify-center">
            <span className="text-sm text-muted-foreground">Cargando…</span>
          </div>
        ) : product ? (
          <>
            <SheetHeader className="mb-6">
              <SheetTitle className="font-mono text-sm text-muted-foreground">
                Editar {sku}
              </SheetTitle>
            </SheetHeader>

            <div className="space-y-5">
              {/* Nombre ES */}
              <div className="space-y-1.5">
                <Label htmlFor="name_es">Nombre (ES)</Label>
                <Input
                  id="name_es"
                  value={draft.name_es}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, name_es: e.target.value }))
                  }
                  placeholder="Nombre en español"
                />
              </div>

              {/* Nombre AR */}
              <div className="space-y-1.5">
                <Label htmlFor="name_ar">Nombre (AR)</Label>
                <Input
                  id="name_ar"
                  value={draft.name_ar}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, name_ar: e.target.value }))
                  }
                  placeholder="Nombre en árabe"
                  dir="rtl"
                />
              </div>

              {/* Marca */}
              <div className="space-y-1.5">
                <Label htmlFor="brand">Marca</Label>
                <Input
                  id="brand"
                  value={draft.brand}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, brand: e.target.value }))
                  }
                  placeholder="—"
                />
              </div>

              {/* GTIN */}
              <div className="space-y-1.5">
                <Label htmlFor="gtin">GTIN</Label>
                <Input
                  id="gtin"
                  value={draft.gtin}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, gtin: e.target.value }))
                  }
                  placeholder="—"
                  maxLength={14}
                  className="font-mono"
                />
              </div>

              {/* Lifecycle Status */}
              <div className="space-y-1.5">
                <Label>Estado lifecycle</Label>
                <Select
                  value={draft.lifecycle_status}
                  onValueChange={(v) =>
                    setDraft((d) => ({
                      ...d,
                      lifecycle_status: v as ProductLifecycleStatus,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LIFECYCLE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Data Quality */}
              <div className="space-y-1.5">
                <Label>Calidad de datos</Label>
                <Select
                  value={draft.data_quality}
                  onValueChange={(v) =>
                    setDraft((d) => ({
                      ...d,
                      data_quality: v as DataQuality,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {QUALITY_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Acceso a formulario completo */}
              <div className="border-t pt-4">
                <a
                  href={`/catalogo/${sku}/edit`}
                  className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                >
                  Editar todos los campos técnicos →
                </a>
              </div>
            </div>

            {/* Footer */}
            <div className="mt-8 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={patchMutation.isPending}
              >
                Cancelar
              </Button>
              <Button onClick={handleSave} disabled={patchMutation.isPending}>
                {patchMutation.isPending ? "Guardando…" : "Guardar"}
              </Button>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
