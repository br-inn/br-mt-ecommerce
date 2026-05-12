"use client";

/**
 * Hooks para la cola de aprobación — US-1B-02-06.
 *
 * Usa @tanstack/react-query (patrón idéntico a use-pricing.ts).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  approvalsApi,
  type ApprovalQueueFilters,
  type PriceDetail,
  type PriceListResponse,
  type PriceRow,
} from "@/lib/api/endpoints/approvals";

// ---- Query keys ------------------------------------------------------------

export const approvalKeys = {
  all: ["approvals"] as const,
  queue: (filters: ApprovalQueueFilters) =>
    ["approvals", "queue", filters] as const,
  detail: (id: string) => ["approvals", "detail", id] as const,
};

// ---- Reads -----------------------------------------------------------------

/** Lista la cola de precios en pending_review. */
export function useApprovalQueue(filters: ApprovalQueueFilters = {}) {
  return useQuery<PriceListResponse, Error>({
    queryKey: approvalKeys.queue(filters),
    queryFn: () => approvalsApi.listQueue(filters),
    staleTime: 20_000,
    refetchInterval: 60_000, // refresca automáticamente cada minuto
  });
}

/** Detalle de un precio (con historial de eventos). */
export function useApprovalDetail(id: string | undefined) {
  return useQuery<PriceDetail, Error>({
    queryKey: approvalKeys.detail(id ?? ""),
    queryFn: () => approvalsApi.getDetail(id as string),
    enabled: !!id,
    staleTime: 10_000,
  });
}

// ---- Mutations -------------------------------------------------------------

/** Aprueba precio individual. */
export function useApproveOne() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) => approvalsApi.approve(id, reason),
    onSuccess: (_, vars) => {
      void qc.invalidateQueries({ queryKey: approvalKeys.all });
      void qc.invalidateQueries({ queryKey: approvalKeys.detail(vars.id) });
      toast.success("Precio aprobado");
    },
    onError: (e) => toast.error(`No se pudo aprobar: ${e.message}`),
  });
}

/** Rechaza precio individual (razón obligatoria ≥10 chars). */
export function useRejectOne() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, { id: string; reason: string }>({
    mutationFn: ({ id, reason }) => approvalsApi.reject(id, reason),
    onSuccess: (_, vars) => {
      void qc.invalidateQueries({ queryKey: approvalKeys.all });
      void qc.invalidateQueries({ queryKey: approvalKeys.detail(vars.id) });
      toast.success("Precio rechazado");
    },
    onError: (e) => toast.error(`No se pudo rechazar: ${e.message}`),
  });
}

/** Revisa precio con nuevo monto. */
export function useReviseOne() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, { id: string; newAmount: string; reason: string }>({
    mutationFn: ({ id, newAmount, reason }) =>
      approvalsApi.revise(id, newAmount, reason),
    onSuccess: (_, vars) => {
      void qc.invalidateQueries({ queryKey: approvalKeys.all });
      void qc.invalidateQueries({ queryKey: approvalKeys.detail(vars.id) });
      toast.success("Precio revisado — nueva propuesta generada");
    },
    onError: (e) => toast.error(`No se pudo revisar: ${e.message}`),
  });
}

/** Bulk-approve. `comment` obligatorio ≥10 chars (backend lo valida también). */
export function useBulkApprove() {
  const qc = useQueryClient();
  return useMutation<
    { approved: number; failed: number; errors: string[] },
    Error,
    { ids: string[]; comment: string }
  >({
    mutationFn: ({ ids, comment }) => approvalsApi.bulkApprove(ids, comment),
    onSuccess: (data, vars) => {
      void qc.invalidateQueries({ queryKey: approvalKeys.all });
      toast.success(
        `${data.approved ?? vars.ids.length} precio${vars.ids.length !== 1 ? "s" : ""} aprobado${vars.ids.length !== 1 ? "s" : ""}`,
      );
      if (data.failed > 0) {
        toast.warning(`${data.failed} no se pudieron aprobar`);
      }
    },
    onError: (e) => toast.error(`Bulk-approve falló: ${e.message}`),
  });
}
