"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProduct } from "@/lib/hooks/products/use-product";
import { ProductWizard } from "../../_components/product-wizard";

/**
 * Edit wizard parity (Sprint 1.5, US-1A-02-04-S2).
 *
 * Reusa `ProductWizard` con `mode="edit"`: misma estructura de 4 steps que
 * el alta, con SKU read-only en step 0 y diff preview en step 4.
 */
export function EditClient({ sku }: { sku: string }) {
  const { data: product, isLoading, isError } = useProduct(sku);

  if (isLoading || (!product && !isError)) {
    return <Skeleton className="h-96 w-full rounded-lg" />;
  }

  if (isError || !product) {
    return null;
  }

  return <ProductWizard mode="edit" product={product} />;
}
