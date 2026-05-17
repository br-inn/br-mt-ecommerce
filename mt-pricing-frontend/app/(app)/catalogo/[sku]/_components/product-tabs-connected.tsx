"use client";

import { useProduct } from "@/lib/hooks/products/use-product";
import { ProductTabs } from "./product-tabs";

interface Props {
  sku: string;
}

export function ProductTabsConnected({ sku }: Props) {
  const { data: product } = useProduct(sku);
  return (
    <ProductTabs
      sku={sku}
      hasImage={product ? !!product.primary_image_url : true}
    />
  );
}
