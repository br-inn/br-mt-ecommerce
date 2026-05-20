"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  matchesApi,
  type MatchAgentConfig,
  type MatchAgentConfigUpdate,
  type MatchAgentMetrics,
  type MatchCandidate,
} from "@/lib/api/endpoints/matches";

import { matchKeys } from "./use-matches";

export function useAgentConfig() {
  return useQuery<MatchAgentConfig, Error>({
    queryKey: ["matches", "agent-config"],
    queryFn: () => matchesApi.agentConfig(),
    staleTime: 60_000,
  });
}

export function useAgentMetrics() {
  return useQuery<MatchAgentMetrics, Error>({
    queryKey: ["matches", "agent-metrics"],
    queryFn: () => matchesApi.agentMetrics(),
    staleTime: 30_000,
  });
}

export function useUpdateAgentConfig() {
  const qc = useQueryClient();
  return useMutation<MatchAgentConfig, Error, MatchAgentConfigUpdate>({
    mutationFn: (body) => matchesApi.updateAgentConfig(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["matches", "agent-config"] });
      void qc.invalidateQueries({ queryKey: ["matches", "agent-metrics"] });
      toast.success("Configuración del agente actualizada");
    },
    onError: (e) => toast.error(`No se pudo actualizar: ${e.message}`),
  });
}

export function useRevertMatch() {
  const qc = useQueryClient();
  return useMutation<MatchCandidate, Error, string>({
    mutationFn: (id) => matchesApi.revert(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: matchKeys.all });
      toast.success("Decisión del agente revertida");
    },
    onError: (e) => toast.error(`No se pudo revertir: ${e.message}`),
  });
}
