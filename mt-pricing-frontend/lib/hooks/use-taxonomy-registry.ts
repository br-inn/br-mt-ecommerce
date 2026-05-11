"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  taxonomyRegistryApi,
  type ProductTaxonomyLinkRead,
  type TaxonomyNodeCreatePayload,
  type TaxonomyNodeRead,
  type TaxonomyNodeUpdatePayload,
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

/**
 * Mutation: crear nodo. Invalida la lista del type tras éxito.
 */
export function useCreateTaxonomyNode(typeSlug: string) {
  const qc = useQueryClient();
  return useMutation<TaxonomyNodeRead, Error, TaxonomyNodeCreatePayload>({
    mutationFn: (payload) =>
      taxonomyRegistryApi.createNode(typeSlug, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.nodes(typeSlug) });
    },
  });
}

/**
 * Mutation: patch parcial de un nodo. El nodeSlug se pasa en el variables
 * para soportar editar varios nodos sin re-renderizar el hook.
 */
export function useUpdateTaxonomyNode(typeSlug: string) {
  const qc = useQueryClient();
  return useMutation<
    TaxonomyNodeRead,
    Error,
    { nodeSlug: string; payload: TaxonomyNodeUpdatePayload }
  >({
    mutationFn: ({ nodeSlug, payload }) =>
      taxonomyRegistryApi.updateNode(typeSlug, nodeSlug, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.nodes(typeSlug) });
    },
  });
}

/**
 * Mutation: soft-delete. Devuelve void (204 No Content del backend).
 */
export function useDeleteTaxonomyNode(typeSlug: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (nodeSlug) =>
      taxonomyRegistryApi.deleteNode(typeSlug, nodeSlug),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.nodes(typeSlug) });
    },
  });
}

export const taxonomyRegistryKeys = KEYS;
