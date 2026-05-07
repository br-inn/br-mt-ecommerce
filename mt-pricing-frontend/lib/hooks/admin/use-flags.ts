"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  adminFlagsApi,
  type AdminFlag,
  type AdminFlagPatchPayload,
  type AdminKillSwitchPayload,
  type AdminKillSwitchResponse,
} from "@/lib/api/endpoints/admin-flags";

const KEYS = {
  all: () => ["admin-flags"] as const,
  list: () => [...KEYS.all(), "list"] as const,
};

/** Listado de feature flags + kill-switches. */
export function useAdminFlags() {
  return useQuery<AdminFlag[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => adminFlagsApi.list(),
    staleTime: 15_000,
  });
}

/** PATCH a un flag concreto. */
export function usePatchAdminFlag(key: string) {
  const qc = useQueryClient();
  return useMutation<AdminFlag, Error, AdminFlagPatchPayload>({
    mutationFn: (payload) => adminFlagsApi.patch(key, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

/** POST kill-switch global — fuerza todos los flags `is_kill_switch` a OFF. */
export function useKillSwitch() {
  const qc = useQueryClient();
  return useMutation<AdminKillSwitchResponse, Error, AdminKillSwitchPayload>({
    mutationFn: (payload) => adminFlagsApi.killSwitch(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

export const adminFlagsKeys = KEYS;
