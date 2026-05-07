"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  isRecalcPreview,
  pricingEngineApi,
  type BulkPublishPayload,
  type BulkPublishResult,
  type ProgressEvent,
  type RecalcPayload,
  type RecalcPreview,
  type RecalcResult,
} from "@/lib/api/endpoints/pricing-engine";
import { pricingKeys } from "@/lib/hooks/pricing/use-pricing";

// ---- Query keys -----------------------------------------------------------

export const pricingEngineKeys = {
  all: ["pricing-engine"] as const,
  taskProgress: (taskId: string | undefined) =>
    [...pricingEngineKeys.all, "progress", taskId ?? ""] as const,
};

// ---- Mutations ------------------------------------------------------------

export function useBulkPublish() {
  const qc = useQueryClient();
  return useMutation<BulkPublishResult, Error, BulkPublishPayload>({
    mutationFn: (payload) => pricingEngineApi.bulkPublish(payload),
    onSuccess: (data, vars) => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success(
        `Publicación encolada · ${vars.price_ids.length} propuesta(s) (job ${data.task_id.slice(0, 8)})`,
      );
    },
    onError: (e) => toast.error(`Bulk-publish falló: ${e.message}`),
  });
}

export function useReviseProposal(priceId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<unknown, Error, { newAmount: string; reason: string }>({
    mutationFn: ({ newAmount, reason }) => {
      if (!priceId) throw new Error("price_id required");
      return pricingEngineApi.revise(priceId, newAmount, reason);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      if (priceId) {
        void qc.invalidateQueries({ queryKey: pricingKeys.detail(priceId) });
      }
      toast.success("Propuesta revisada");
    },
    onError: (e) => toast.error(`Revise falló: ${e.message}`),
  });
}

export function useRecalculateBatch() {
  const qc = useQueryClient();
  return useMutation<RecalcResult | RecalcPreview, Error, RecalcPayload>({
    mutationFn: (payload) => pricingEngineApi.recalculate(payload),
    onSuccess: (data, vars) => {
      if (isRecalcPreview(data)) {
        // dry_run: no invalidamos cache, sólo informamos
        return;
      }
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success(
        vars.scope === "single"
          ? "Recálculo completado"
          : `Recálculo encolado · job ${data.task_id.slice(0, 8)}`,
      );
    },
    onError: (e) => toast.error(`Recálculo falló: ${e.message}`),
  });
}

// ---- Polling hook (progress) ---------------------------------------------

/**
 * Polling de progreso de un job. Refresca cada 2 s mientras el status no sea
 * terminal (success/failed). Devuelve undefined hasta que llega el primer
 * snapshot.
 */
export function useTaskProgress(
  taskId: string | undefined,
  enabled = true,
) {
  return useQuery<ProgressEvent, Error>({
    queryKey: pricingEngineKeys.taskProgress(taskId),
    queryFn: () => pricingEngineApi.taskProgress(taskId as string),
    enabled: enabled && !!taskId,
    refetchInterval: (q) => {
      const data = q.state.data as ProgressEvent | undefined;
      if (!data) return 2000;
      if (data.status === "success" || data.status === "failed") return false;
      return 2000;
    },
    staleTime: 0,
  });
}
