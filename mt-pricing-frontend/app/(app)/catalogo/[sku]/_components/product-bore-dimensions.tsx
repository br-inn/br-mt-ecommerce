"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProductBoreDimensions } from "@/lib/hooks/products/use-bore-dimensions";
import type { BoreDimension } from "@/lib/api/endpoints/products";

function DimCell({ value, unit }: { value: number | null | undefined; unit?: string }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  return <span>{value}{unit ? <span className="ml-0.5 text-xs text-muted-foreground">{unit}</span> : null}</span>;
}

function DimensionRow({ row }: { row: BoreDimension }) {
  return (
    <tr className="border-b last:border-b-0 hover:bg-muted/30 transition-colors">
      <td className="py-2 pr-3 align-top">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">{row.standard_code}</span>
          {row.pressure_class ? (
            <span className="text-xs text-muted-foreground">{row.pressure_class}</span>
          ) : null}
        </div>
      </td>
      <td className="py-2 pr-3 align-middle">
        <Badge variant="secondary" className="text-[10px] font-mono">{row.standard_system}</Badge>
        {row.is_primary ? (
          <Badge variant="default" className="ml-1 text-[10px]">Principal</Badge>
        ) : null}
      </td>
      <td className="py-2 pr-3 text-right align-middle text-sm tabular-nums">
        <DimCell value={row.bore_mm != null ? Number(row.bore_mm) : null} unit="mm" />
      </td>
      <td className="py-2 pr-3 text-right align-middle text-sm tabular-nums">
        <DimCell value={row.face_to_face_mm != null ? Number(row.face_to_face_mm) : null} unit="mm" />
      </td>
      <td className="py-2 pr-3 text-right align-middle text-sm tabular-nums">
        <DimCell value={row.end_to_end_mm != null ? Number(row.end_to_end_mm) : null} unit="mm" />
      </td>
      <td className="py-2 pr-3 text-right align-middle text-sm tabular-nums">
        <DimCell value={row.flange_od_mm != null ? Number(row.flange_od_mm) : null} unit="mm" />
      </td>
      <td className="py-2 pr-3 text-right align-middle text-sm tabular-nums">
        <DimCell value={row.bolt_circle_mm != null ? Number(row.bolt_circle_mm) : null} unit="mm" />
      </td>
      <td className="py-2 align-middle text-sm">
        {row.bolt_count != null || row.bolt_size ? (
          <span className="text-muted-foreground">
            {row.bolt_count != null ? `${row.bolt_count}×` : ""}
            {row.bolt_size ?? ""}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

export function ProductBoreDimensions({ sku }: { sku: string }) {
  const { data, isLoading, isError } = useProductBoreDimensions(sku);

  if (isLoading) {
    return <Skeleton className="h-40 w-full rounded-lg" />;
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive">Error al cargar dimensiones por norma.</p>
    );
  }

  if (!data || data.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dimensiones por Norma</CardTitle>
        <CardDescription>EN 558, ASME B16.10, AWWA C504 y otras normas aplicables.</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[700px] border-collapse px-4">
          <thead>
            <tr className="border-b bg-muted/50">
              <th scope="col" className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Norma / Código
              </th>
              <th scope="col" className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Sistema
              </th>
              <th scope="col" className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Bore
              </th>
              <th scope="col" className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Cara–Cara
              </th>
              <th scope="col" className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Extrem–Extrem
              </th>
              <th scope="col" className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Ø Brida
              </th>
              <th scope="col" className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Ø Pernos
              </th>
              <th scope="col" className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Pernos
              </th>
            </tr>
          </thead>
          <tbody className="divide-y px-3">
            {data.map((row) => (
              <DimensionRow key={row.id} row={row} />
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
