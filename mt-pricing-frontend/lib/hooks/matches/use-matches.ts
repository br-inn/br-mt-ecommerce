"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  useInfiniteQuery,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  matchesApi,
  type MatchCandidate,
  type MatchCandidateDetail,
  type MatchFilters,
  type MatchListResponse,
  type MatchRefreshResponse,
} from "@/lib/api/endpoints/matches";

const DEFAULT_LIMIT = 25;

export const matchKeys = {
  all: ["matches"] as const,
  list: (filters: MatchFilters) => ["matches", "list", filters] as const,
  detail: (id: string) => ["matches", "detail", id] as const,
};

export function useMatches(filters: MatchFilters = {}) {
  return useInfiniteQuery<
    MatchListResponse,
    Error,
    { pages: MatchListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof matchKeys.list>,
    string | null
  >({
    queryKey: matchKeys.list(filters),
    queryFn: ({ pageParam }) =>
      matchesApi.list({
        ...filters,
        cursor: pageParam,
        limit: filters.limit ?? DEFAULT_LIMIT,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor.next ?? undefined,
    staleTime: 30_000,
  });
}

export function useMatchDetail(id: string | undefined) {
  return useQuery<MatchCandidateDetail, Error>({
    queryKey: matchKeys.detail(id ?? ""),
    queryFn: () => matchesApi.get(id as string),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useRefreshMatches() {
  const qc = useQueryClient();
  return useMutation<MatchRefreshResponse, Error, string>({
    mutationFn: (sku) => matchesApi.refresh(sku),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success(`Scraper devolvió ${data.refreshed_count} candidatos para ${data.sku}`);
    },
    onError: (e) => toast.error(`Refresh falló: ${e.message}`),
  });
}

export function useValidateMatch() {
  const qc = useQueryClient();
  return useMutation<MatchCandidate, Error, string>({
    mutationFn: (id) => matchesApi.validate(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success("Match validado");
    },
    onError: (e) => toast.error(`No se pudo validar: ${e.message}`),
  });
}

export function useDiscardMatch() {
  const qc = useQueryClient();
  return useMutation<MatchCandidate, Error, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) => matchesApi.discard(id, reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success("Candidato descartado");
    },
    onError: (e) => toast.error(`No se pudo descartar: ${e.message}`),
  });
}
