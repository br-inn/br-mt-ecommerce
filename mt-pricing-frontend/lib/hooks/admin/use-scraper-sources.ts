"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  scraperSourcesApi,
  type ActivateRequest,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type RecipeCreate,
  type RecipeRead,
  type ScraperSourceCreate,
  type ScraperSourceRead,
  type ScraperSourceUpdate,
  type ValidateRequest,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";

const KEYS = {
  all: () => ["scraper-sources"] as const,
  list: () => [...KEYS.all(), "list"] as const,
  recipes: (sourceId: string) => [...KEYS.all(), sourceId, "recipes"] as const,
};

export function useScraperSources() {
  return useQuery({
    queryKey: KEYS.list(),
    queryFn: () => scraperSourcesApi.list(),
    staleTime: 30_000,
  });
}

export function useCreateScraperSource() {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, ScraperSourceCreate>({
    mutationFn: (req) => scraperSourcesApi.create(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useUpdateScraperSource() {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, { id: string; data: ScraperSourceUpdate }>({
    mutationFn: ({ id, data }) => scraperSourcesApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useScraperSourceRecipes(sourceId: string | null) {
  return useQuery<RecipeRead[]>({
    queryKey: sourceId ? KEYS.recipes(sourceId) : ["scraper-sources", "__none__", "recipes"],
    queryFn: () => scraperSourcesApi.listRecipes(sourceId!),
    enabled: sourceId !== null,
    staleTime: 60_000,
  });
}

export function useCreateRecipe(sourceId: string) {
  const qc = useQueryClient();
  return useMutation<RecipeRead, Error, RecipeCreate>({
    mutationFn: (req) => scraperSourcesApi.createRecipe(sourceId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.recipes(sourceId) }),
  });
}

export function useValidateRecipe(sourceId: string) {
  return useMutation<ValidateResponse, Error, ValidateRequest>({
    mutationFn: (req) => scraperSourcesApi.validate(sourceId, req),
  });
}

export function useActivateSource(sourceId: string) {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, ActivateRequest>({
    mutationFn: (req) => scraperSourcesApi.activate(sourceId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export const scraperSourceKeys = KEYS;

export function useAnalyzeUrl() {
  return useMutation<AnalyzeResponse, Error, AnalyzeRequest>({
    mutationFn: (req) => scraperSourcesApi.analyze(req),
  });
}
