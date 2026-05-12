"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  exceptionRulesApi,
  type ExceptionRuleCreatePayload,
  type ExceptionRuleRow,
} from "@/lib/api/endpoints/exception-rules";

const KEYS = {
  all: () => ["exception-rules"] as const,
  active: () => [...KEYS.all(), "active"] as const,
  history: (limit?: number) => [...KEYS.all(), "history", limit] as const,
};

/** Lista de reglas activas. */
export function useExceptionRulesActive() {
  return useQuery<ExceptionRuleRow[], Error>({
    queryKey: KEYS.active(),
    queryFn: () => exceptionRulesApi.listActive(),
    staleTime: 60_000,
  });
}

/** Historial completo (activas + cerradas). */
export function useExceptionRulesHistory(limit = 50) {
  return useQuery<ExceptionRuleRow[], Error>({
    queryKey: KEYS.history(limit),
    queryFn: () => exceptionRulesApi.listHistory(limit),
    staleTime: 30_000,
  });
}

/** Crea nueva regla (inactiva por defecto). */
export function useCreateExceptionRule() {
  const qc = useQueryClient();
  return useMutation<ExceptionRuleRow, Error, ExceptionRuleCreatePayload>({
    mutationFn: (payload) => exceptionRulesApi.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

/** Activa una regla y cierra la versión anterior del mismo scope. */
export function useActivateExceptionRule() {
  const qc = useQueryClient();
  return useMutation<ExceptionRuleRow, Error, string>({
    mutationFn: (ruleId) => exceptionRulesApi.activate(ruleId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
    },
  });
}

export const exceptionRulesQueryKeys = KEYS;
