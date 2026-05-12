"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  channelsAdminApi,
  ChannelsAdminApiError,
  STATIC_CHANNELS,
  type Channel,
  type ChannelStateHistoryEntry,
  type ChannelTransitionRequest,
  type ChannelTransitionResponse,
} from "@/lib/api/endpoints/channels-admin";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

const KEYS = {
  all: () => ["channels-admin"] as const,
  list: () => [...KEYS.all(), "list"] as const,
  history: (id: string) => [...KEYS.all(), "history", id] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Lista de canales. Cae a estáticos si el endpoint no existe aún (404/405). */
export function useChannels() {
  return useQuery<Channel[], Error>({
    queryKey: KEYS.list(),
    queryFn: async () => {
      try {
        return await channelsAdminApi.list();
      } catch (err) {
        // Endpoint GET /channels aún no implementado → usar fallback estático
        if (
          err instanceof ChannelsAdminApiError &&
          (err.status === 404 || err.status === 405 || err.status === 422)
        ) {
          return STATIC_CHANNELS;
        }
        // Para cualquier otro error (red, 500) relanzar
        throw err;
      }
    },
    staleTime: 30_000,
  });
}

/** Historial de transiciones de un canal. Devuelve [] si el endpoint no existe. */
export function useChannelHistory(channelId: string | null) {
  return useQuery<ChannelStateHistoryEntry[], Error>({
    queryKey: KEYS.history(channelId ?? ""),
    enabled: !!channelId,
    queryFn: async () => {
      if (!channelId) return [];
      try {
        return await channelsAdminApi.history(channelId);
      } catch (err) {
        if (
          err instanceof ChannelsAdminApiError &&
          (err.status === 404 || err.status === 405)
        ) {
          return [];
        }
        throw err;
      }
    },
    staleTime: 15_000,
  });
}

/** Mutación de transición de estado. */
export function useTransitionChannel() {
  const qc = useQueryClient();
  return useMutation<
    ChannelTransitionResponse,
    ChannelsAdminApiError,
    { channelId: string; payload: ChannelTransitionRequest }
  >({
    mutationFn: ({ channelId, payload }) =>
      channelsAdminApi.transition(channelId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.list() });
    },
  });
}

export { type Channel, type ChannelStateHistoryEntry, type ChannelTransitionResponse };
export { KEYS as channelsAdminKeys };
