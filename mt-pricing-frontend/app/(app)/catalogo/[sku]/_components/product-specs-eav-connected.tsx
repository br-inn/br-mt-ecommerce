"use client";

import { useProduct } from "@/lib/hooks/products/use-product";
import { ProductSpecsCardEAV } from "./product-specs-eav";

/**
 * Wrapper client component que resuelve `family_id` desde el detalle del
 * producto (Fase B) y se lo pasa al card EAV. Si el producto aún no está
 * cargado o no tiene `family_id`, el card downstream maneja el placeholder.
 */
export function ProductSpecsCardEAVConnected({ sku }: { sku: string }) {
  const { data: product } = useProduct(sku);
  const familyId = product?.family_id ?? null;
  if (!familyId) return null;
  return <ProductSpecsCardEAV sku={sku} familyId={familyId} />;
}
