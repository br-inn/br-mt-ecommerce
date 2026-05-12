"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils/cn";
import { useSparePartsForSeries } from "@/lib/hooks/use-spare-parts";
import type {
  CompatibilityKind,
  ProductCompatibility,
} from "@/lib/api/endpoints/products";

interface Props {
  seriesId: string;
  className?: string;
  /** Valor inicial opcional del filtro DN. */
  initialDn?: number;
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

/**
 * Navegador de recambios aplicables a una serie (Fase 5).
 *
 * Renderiza la lista devuelta por
 * `GET /api/v1/series/{series_id}/spare-parts?dn={dn}` y permite filtrar por
 * un DN concreto (calibre). Cada fila muestra el SKU/nombre del producto
 * recambio, el rango DN aplicable (badge) y el tipo de relación.
 */
export function SeriesSparePartsBrowser({
  seriesId,
  className,
  initialDn,
}: Props) {
  const [dnInput, setDnInput] = React.useState<string>(
    initialDn != null ? String(initialDn) : "",
  );

  const parsedDn = React.useMemo<number | undefined>(() => {
    if (dnInput.trim() === "") return undefined;
    const n = Number(dnInput);
    return Number.isFinite(n) && n >= 0 ? n : undefined;
  }, [dnInput]);

  const { data, isLoading, isError, error } = useSparePartsForSeries(
    seriesId,
    parsedDn,
  );

  const rows = data ?? [];

  return (
    <section className={cn("space-y-4", className)} aria-label="Recambios de la serie">
      <div className="flex max-w-xs items-end gap-2">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="dn-filter">Filtrar por DN</Label>
          <Input
            id="dn-filter"
            type="number"
            min={0}
            max={10000}
            value={dnInput}
            onChange={(e) => setDnInput(e.target.value)}
            placeholder="DN (vacío = todos)"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2" data-testid="spare-parts-loading">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : isError ? (
        <p role="alert" className="text-sm text-destructive">
          Error al cargar recambios: {error?.message ?? "desconocido"}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="spare-parts-empty">
          Sin recambios para esta serie
          {parsedDn != null ? ` en DN ${parsedDn}` : ""}.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Rango DN</TableHead>
              <TableHead>Tipo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row: ProductCompatibility) => (
              <TableRow key={row.id} data-testid={`spare-part-${row.compatible_with_sku}`}>
                <TableCell className="font-mono text-xs">
                  {row.compatible_with_sku}
                </TableCell>
                <TableCell>
                  {row.compatible_product?.display_name ?? row.compatible_with_sku}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {formatRange(row.dn_min, row.dn_max)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge>{KIND_LABELS[row.kind]}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

export default SeriesSparePartsBrowser;
