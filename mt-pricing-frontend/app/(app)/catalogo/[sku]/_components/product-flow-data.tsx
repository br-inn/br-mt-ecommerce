"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProductFlowData } from "@/lib/hooks/products/use-product-model";

export function ProductFlowData({ sku }: { sku: string }) {
  const { data: rows, isLoading } = useProductFlowData(sku);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!rows?.length) return null;

  return (
    <section aria-label="Coeficientes de flujo" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Coeficientes de flujo
      </h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium">DN (mm)</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Kv (m³/h)</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Cv</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Malla (mm)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{r.dn_mm}</td>
                <td className="px-3 py-2 text-right text-xs">{r.kv ?? "—"}</td>
                <td className="px-3 py-2 text-right text-xs">{r.cv ?? "—"}</td>
                <td className="px-3 py-2 text-right text-xs">{r.mesh_mm ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
