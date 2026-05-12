"use client";

/**
 * Tab "Recambios / Compatibilidad" del SKU detail (Fase 5).
 *
 * Lista los enlaces de compatibility outgoing del producto y ofrece un form
 * para añadir uno nuevo con owner_type polymorphic + DN range opcional.
 */

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { SparePartCompatibilityForm } from "@/components/domain/spare-part-compatibility-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  productsApi,
  ProductsApiError,
  type CompatibilityKind,
  type ProductCompatibility,
  type ProductCompatibilityCreate,
} from "@/lib/api/endpoints/products";

interface Props {
  sku: string;
}

const KIND_LABELS: Record<CompatibilityKind, string> = {
  spare_part: "Recambio",
  accessory: "Accesorio",
  replaces: "Reemplaza a",
  replaced_by: "Reemplazado por",
  compatible_with: "Compatible con",
};

function formatRange(min: number | null, max: number | null): string {
  if (min == null && max == null) return "—";
  if (min != null && max != null) return `DN ${min}–${max}`;
  if (min != null) return `DN ≥ ${min}`;
  return `DN ≤ ${max}`;
}

export function ProductCompatibilityTabClient({ sku }: Props) {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery<
    ProductCompatibility[],
    Error
  >({
    queryKey: ["products", "detail", sku, "compatibility"],
    queryFn: () => productsApi.listCompatibility(sku),
    enabled: !!sku,
    staleTime: 30_000,
  });

  const addMutation = useMutation<
    ProductCompatibility,
    Error,
    ProductCompatibilityCreate
  >({
    mutationFn: (payload) => productsApi.addCompatibility(sku, payload),
    onSuccess: () => {
      toast.success("Enlace añadido");
      queryClient.invalidateQueries({
        queryKey: ["products", "detail", sku, "compatibility"],
      });
    },
    onError: (err) => {
      toast.error(err.message);
    },
  });

  const removeMutation = useMutation<
    void,
    Error,
    { compatibleWithSku: string; kind: CompatibilityKind }
  >({
    mutationFn: ({ compatibleWithSku, kind }) =>
      productsApi.removeCompatibility(sku, compatibleWithSku, kind),
    onSuccess: () => {
      toast.success("Enlace eliminado");
      queryClient.invalidateQueries({
        queryKey: ["products", "detail", sku, "compatibility"],
      });
    },
    onError: (err) => {
      toast.error(err.message);
    },
  });

  const errorMessage = addMutation.error
    ? addMutation.error instanceof ProductsApiError
      ? addMutation.error.message
      : addMutation.error.message
    : null;

  const rows = data ?? [];

  return (
    <section className="space-y-6 p-4" aria-label="Recambios y compatibilidad">
      <header>
        <h2 className="text-lg font-semibold">Recambios y compatibilidad</h2>
        <p className="text-sm text-muted-foreground">
          Enlaces outgoing desde <span className="font-mono">{sku}</span>.
        </p>
      </header>

      <div className="rounded-md border bg-card p-4">
        <h3 className="mb-3 text-sm font-medium">Añadir enlace</h3>
        <SparePartCompatibilityForm
          sku={sku}
          onSubmit={async (payload) => {
            await addMutation.mutateAsync(payload);
          }}
          isSaving={addMutation.isPending}
          errorMessage={errorMessage}
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : isError ? (
        <p role="alert" className="text-sm text-destructive">
          Error: {error?.message ?? "desconocido"}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin enlaces todavía.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead>Rango DN</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-mono text-xs">
                  {row.compatible_with_sku}
                </TableCell>
                <TableCell>
                  {row.compatible_product?.display_name ?? "—"}
                </TableCell>
                <TableCell>
                  <Badge>{KIND_LABELS[row.kind]}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{row.owner_type}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {formatRange(row.dn_min, row.dn_max)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={removeMutation.isPending}
                    onClick={() =>
                      removeMutation.mutate({
                        compatibleWithSku: row.compatible_with_sku,
                        kind: row.kind,
                      })
                    }
                  >
                    Eliminar
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

export default ProductCompatibilityTabClient;
