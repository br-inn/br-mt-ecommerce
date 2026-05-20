"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProduct } from "@/lib/hooks/products/use-product";
import { useProductFlowData } from "@/lib/hooks/products/use-product-model";

export function ProductFlowData({ sku }: { sku: string }) {
  const { data: product } = useProduct(sku);
  const { data: rows, isLoading } = useProductFlowData(sku);

  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (!rows?.length) return null;

  const productDn = product?.dn != null ? parseInt(product.dn, 10) : null;
  const row =
    productDn != null
      ? (rows.find((r) => r.dn_mm === productDn) ?? rows[0])
      : rows[0];

  if (!row) return null;

  return (
    <section aria-label="Coeficientes de flujo" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Coeficientes de flujo
      </h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th scope="col" className="px-3 py-2 text-right text-xs font-medium">Kv (m³/h)</th>
              <th scope="col" className="px-3 py-2 text-right text-xs font-medium">Cv</th>
              <th scope="col" className="px-3 py-2 text-right text-xs font-medium">Malla (mm)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-3 py-2 text-right text-xs">{row.kv ?? "—"}</td>
              <td className="px-3 py-2 text-right text-xs">{row.cv ?? "—"}</td>
              <td className="px-3 py-2 text-right text-xs">{row.mesh_mm ?? "—"}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
