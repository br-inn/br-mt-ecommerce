"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  adminCalibratorApi,
  type CalibratorActiveResponse,
  type CalibratorPromoteResponse,
  type CalibratorTrainPayload,
  type CalibratorTrainResponse,
} from "@/lib/api/endpoints/admin-calibrator";

const KEYS = {
  all: () => ["admin-calibrator"] as const,
  active: () => [...KEYS.all(), "active"] as const,
};

/** Versión activa del calibrator + listado de versiones disponibles. */
export function useCalibratorActive() {
  return useQuery<CalibratorActiveResponse, Error>({
    queryKey: KEYS.active(),
    queryFn: () => adminCalibratorApi.active(),
    staleTime: 30_000,
  });
}

/** Encola un train ad-hoc del calibrator (Celery task). */
export function useTrainCalibrator() {
  const qc = useQueryClient();
  return useMutation<CalibratorTrainResponse, Error, CalibratorTrainPayload>({
    mutationFn: (payload) => adminCalibratorApi.train(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

/** Promueve una versión a active (cierra la anterior). */
export function usePromoteCalibrator() {
  const qc = useQueryClient();
  return useMutation<CalibratorPromoteResponse, Error, { version: string }>({
    mutationFn: ({ version }) => adminCalibratorApi.promote(version),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

export const adminCalibratorKeys = KEYS;
