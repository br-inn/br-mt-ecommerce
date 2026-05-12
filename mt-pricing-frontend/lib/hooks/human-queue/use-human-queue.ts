"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  humanQueueApi,
  type HumanQueueFilters,
  type HumanQueueItem,
  type HumanQueueListResponse,
  type LabelPayload,
} from "@/lib/api/endpoints/human-queue";

const KEYS = {
  all: () => ["human-queue"] as const,
  list: (filters: HumanQueueFilters) =>
    [...KEYS.all(), "list", filters] as const,
};

/** Lista la cola de validación humana con filtros de paginación y threshold. */
export function useHumanQueue(filters: HumanQueueFilters = {}) {
  return useQuery<HumanQueueListResponse, Error>({
    queryKey: KEYS.list(filters),
    queryFn: () => humanQueueApi.list(filters),
    staleTime: 30_000,
  });
}

/** Aplica un label (accept/reject/skip) a un match candidate. */
export function useLabelMatch() {
  const qc = useQueryClient();
  return useMutation<
    HumanQueueItem,
    Error,
    { matchId: string; payload: LabelPayload }
  >({
    mutationFn: ({ matchId, payload }) => humanQueueApi.label(matchId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}
