"use client";

import * as React from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  useInfiniteQuery,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  matchesApi,
  type MatchBulkValidateResponse,
  type MatchCandidate,
  type MatchCandidateDetail,
  type MatchFilters,
  type MatchListResponse,
  type MatchRefreshJobResponse,
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
  const [pollingTask, setPollingTask] = React.useState<{ sku: string; taskId: string } | null>(null);

  // Polling — activo solo cuando hay una task en vuelo.
  const { data: pollData } = useQuery({
    queryKey: ["matches", "refresh-status", pollingTask?.taskId],
    queryFn: () => matchesApi.refreshStatus(pollingTask!.sku, pollingTask!.taskId),
    enabled: !!pollingTask,
    refetchInterval: (query) => {
      const s = query.state.data?.task_status;
      return s === "done" || s === "failed" ? false : 3000;
    },
  });

  React.useEffect(() => {
    if (!pollData) return;
    if (pollData.task_status === "done") {
      setPollingTask(null);
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success(`Scraper encontró ${pollData.refreshed_count} candidatos para ${pollData.sku}`);
    } else if (pollData.task_status === "failed") {
      setPollingTask(null);
      toast.error(`El scraper falló: ${pollData.error ?? "error desconocido"}`);
    }
  }, [pollData?.task_status, pollData?.sku, pollData?.refreshed_count, pollData?.error, qc]);

  const mutation = useMutation<MatchRefreshJobResponse, Error, string>({
    mutationFn: (sku) => matchesApi.refresh(sku),
    onSuccess: (data) => {
      if (data.task_status === "done") {
        void qc.invalidateQueries({ queryKey: matchKeys.all });
        toast.success(`Scraper encontró ${data.refreshed_count} candidatos para ${data.sku}`);
      } else {
        setPollingTask({ sku: data.sku, taskId: data.task_id });
        toast.info("Scraping en curso — se actualizará automáticamente al terminar.");
      }
    },
    onError: (e) => toast.error(`Refresh falló: ${e.message}`),
  });

  return { ...mutation, isPolling: !!pollingTask };
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

export function useBulkValidateMatches() {
  const qc = useQueryClient();
  return useMutation<MatchBulkValidateResponse, Error, string[]>({
    mutationFn: (ids) => matchesApi.bulkValidate(ids),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      const msg =
        res.skipped.length > 0
          ? `${res.validated} validados · ${res.skipped.length} omitidos`
          : `${res.validated} candidatos validados`;
      toast.success(msg);
    },
    onError: (e) => toast.error(`No se pudieron validar: ${e.message}`),
  });
}
