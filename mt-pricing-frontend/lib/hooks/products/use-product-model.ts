"use client";

import { useQuery } from "@tanstack/react-query";
import { productsApi, type ProductComponentMaterial } from "@/lib/api/endpoints/products";

export function useProductCertificates(sku: string) {
  return useQuery({
    queryKey: ["products", sku, "certificates"],
    queryFn: () => productsApi.getCertificates(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}

export function useProductFlowData(sku: string) {
  return useQuery({
    queryKey: ["products", sku, "flow-data"],
    queryFn: () => productsApi.getFlowData(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}

export function useProductMaterials(sku: string) {
  return useQuery<ProductComponentMaterial[]>({
    queryKey: ["products", sku, "materials"],
    queryFn: () => productsApi.getMaterials(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}
