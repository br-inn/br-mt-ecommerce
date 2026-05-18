"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProductMaterials } from "@/lib/hooks/products/use-product-model";
import type { ProductComponentMaterial } from "@/lib/api/endpoints/products";

const COMPONENT_LABELS: Record<string, string> = {
  body: "Cuerpo",
  closure: "Obturador",
  seat: "Asiento",
  gasket: "Junta",
  screen: "Filtro",
  actuator_housing: "Carcasa actuador",
  stem: "Vástago",
  handle: "Palanca",
  other: "Otro",
};

function MaterialRow({ row }: { row: ProductComponentMaterial }) {
  const label = COMPONENT_LABELS[row.component] ?? row.component;
  return (
    <tr className="border-b last:border-b-0 hover:bg-muted/30 transition-colors">
      <td className="py-2 px-3 text-sm font-medium">{label}</td>
      <td className="py-2 px-3 text-sm">{row.material}</td>
      <td className="py-2 px-3 text-sm text-muted-foreground">
        {[row.material_grade, row.material_standard].filter(Boolean).join(" · ") || "—"}
      </td>
      <td className="py-2 px-3 text-sm text-muted-foreground">
        {row.surface_treatment ?? "—"}
      </td>
      <td className="py-2 px-3 text-sm text-muted-foreground">
        {row.observations ?? "—"}
      </td>
    </tr>
  );
}

export function ProductMaterials({ sku }: { sku: string }) {
  const { data, isLoading } = useProductMaterials(sku);

  if (isLoading) return <Skeleton className="h-32 w-full rounded-lg" />;
  if (!data || data.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Materiales por componente</CardTitle>
        <CardDescription>Materiales, grados y tratamientos superficiales de cada componente.</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[600px] border-collapse">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Componente
              </th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Material
              </th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Grado / Norma
              </th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Tratamiento superficial
              </th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Notas
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.map((row) => (
              <MaterialRow key={`${row.component}-${row.position}`} row={row} />
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
