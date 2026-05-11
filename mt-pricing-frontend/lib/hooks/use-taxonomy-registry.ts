"use client";

import { useQuery } from "@tanstack/react-query";

import {
  taxonomyRegistryApi,
  type ProductTaxonomyLinkRead,
  type TaxonomyNodeRead,
  type TaxonomyTypeRead,
} from "@/lib/api/endpoints/taxonomy-registry";

const KEYS = {
  all: () => ["taxonomy-registry"] as const,
  registry: (filterableOnly?: boolean) =>
    [...KEYS.all(), "registry", { filterableOnly }] as const,
  type: (slug: string) => [...KEYS.all(), "type", slug] as const,
  nodes: (typeSlug: string) => [...KEYS.all(), "nodes", typeSlug] as const,
  productLinks: (sku: string) =>
    [...KEYS.all(), "product-links", sku] as const,
};

/**
 * Lista de TaxonomyTypes del registry — drives sidebar SISTEMA y filtros.
 *
 * staleTime alto porque el registry rara vez cambia (config-like).
 */
export function useTaxonomyRegistry(params?: {
  filterableOnly?: boolean;
  enabled?: boolean;
}) {
  return useQuery<TaxonomyTypeRead[], Error>({
    queryKey: KEYS.registry(params?.filterableOnly),
    queryFn: () =>
      taxonomyRegistryApi.listRegistry(
        params?.filterableOnly ? { filterable_only: true } : undefined,
      ),
    staleTime: 5 * 60_000,
    enabled: params?.enabled ?? true,
  });
}

/** Metadatos de un tipo específico. */
export function useTaxonomyType(slug: string, enabled = true) {
  return useQuery<TaxonomyTypeRead, Error>({
    queryKey: KEYS.type(slug),
    queryFn: () => taxonomyRegistryApi.getType(slug),
    enabled: enabled && !!slug,
    staleTime: 5 * 60_000,
  });
}

/** Listar nodos de un tipo. */
export function useTaxonomyNodes(typeSlug: string, enabled = true) {
  return useQuery<TaxonomyNodeRead[], Error>({
    queryKey: KEYS.nodes(typeSlug),
    queryFn: () => taxonomyRegistryApi.listNodes(typeSlug),
    enabled: enabled && !!typeSlug,
    staleTime: 60_000,
  });
}

/** Listar links de un producto. */
export function useProductTaxonomies(
  sku: string,
  params?: { role?: string; typeSlug?: string; enabled?: boolean },
) {
  return useQuery<ProductTaxonomyLinkRead[], Error>({
    queryKey: KEYS.productLinks(sku),
    queryFn: () => {
      const query: { role?: string; type_slug?: string } = {};
      if (params?.role) query.role = params.role;
      if (params?.typeSlug) query.type_slug = params.typeSlug;
      return taxonomyRegistryApi.listForProduct(sku, query);
    },
    enabled: (params?.enabled ?? true) && !!sku,
    staleTime: 30_000,
  });
}

export const taxonomyRegistryKeys = KEYS;
