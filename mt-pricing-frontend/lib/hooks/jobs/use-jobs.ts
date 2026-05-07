"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  jobsAdminApi,
  type JobDefinitionCreatePayload,
  type JobDefinitionDetail,
  type JobDefinitionListItem,
  type JobDefinitionUpdatePayload,
  type JobOwner,
  type JobRunNowResponse,
  type JobRunsPage,
} from "@/lib/api/endpoints/jobs";

export const jobsKeys = {
  all: () => ["jobs-admin"] as const,
  list: (params: {
    enabled?: boolean | undefined;
    owner?: JobOwner | undefined;
  }) => [...jobsKeys.all(), "list", params] as const,
  detail: (id: string) => [...jobsKeys.all(), "detail", id] as const,
  runs: (id: string, offset: number) =>
    [...jobsKeys.all(), "runs", id, offset] as const,
};

export function useJobsList(
  params: {
    enabled?: boolean | undefined;
    owner?: JobOwner | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  } = {},
) {
  return useQuery<JobDefinitionListItem[], Error>({
    queryKey: jobsKeys.list({
      ...(params.enabled !== undefined ? { enabled: params.enabled } : {}),
      ...(params.owner !== undefined ? { owner: params.owner } : {}),
    }),
    queryFn: () => jobsAdminApi.list(params),
    staleTime: 15_000,
  });
}

export function useJobDetail(id: string | undefined) {
  return useQuery<JobDefinitionDetail, Error>({
    queryKey: jobsKeys.detail(id ?? ""),
    queryFn: () => jobsAdminApi.get(id as string),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useJobRuns(id: string | undefined, offset = 0, limit = 50) {
  return useQuery<JobRunsPage, Error>({
    queryKey: jobsKeys.runs(id ?? "", offset),
    queryFn: () => jobsAdminApi.listRuns(id as string, { offset, limit }),
    enabled: !!id,
    refetchInterval: 5000, // poll para ver run-now actualizado
    staleTime: 0,
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation<JobDefinitionDetail, Error, JobDefinitionCreatePayload>({
    mutationFn: (payload) => jobsAdminApi.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: jobsKeys.all() });
    },
  });
}

export function useUpdateJob(id: string) {
  const qc = useQueryClient();
  return useMutation<JobDefinitionDetail, Error, JobDefinitionUpdatePayload>({
    mutationFn: (payload) => jobsAdminApi.update(id, payload),
    onMutate: async (payload) => {
      // Optimistic toggle enabled — sólo aplicamos las claves definidas.
      await qc.cancelQueries({ queryKey: jobsKeys.detail(id) });
      const prev = qc.getQueryData<JobDefinitionDetail>(jobsKeys.detail(id));
      if (prev) {
        const merged: JobDefinitionDetail = { ...prev };
        for (const [k, v] of Object.entries(payload)) {
          if (v !== undefined) {
            (merged as unknown as Record<string, unknown>)[k] = v;
          }
        }
        qc.setQueryData<JobDefinitionDetail>(jobsKeys.detail(id), merged);
      }
      return { prev };
    },
    onError: (_err, _payload, ctx) => {
      const c = ctx as { prev?: JobDefinitionDetail } | undefined;
      if (c?.prev) qc.setQueryData(jobsKeys.detail(id), c.prev);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: jobsKeys.all() });
    },
  });
}

export function useRunJobNow(id: string) {
  const qc = useQueryClient();
  return useMutation<JobRunNowResponse, Error, void>({
    mutationFn: () => jobsAdminApi.runNow(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: jobsKeys.all() });
    },
  });
}

// ---------------------------------------------------------------------------
// Cron preview helper — local, no llama backend. Usa una expansión naive
// (fallback) cuando `cron-parser` no está instalado. Soporta los patrones
// más comunes para preview UI.
// ---------------------------------------------------------------------------
export function cronPreviewNext(
  cron: string | null | undefined,
  count = 5,
): Date[] {
  if (!cron) return [];
  const parts = cron.trim().split(/\s+/);
  if (parts.length < 5) return [];
  const [minPart, hourPart, domPart, monPart, dowPart] = parts;
  const now = new Date();
  const out: Date[] = [];

  const inSet = (val: number, expr: string, max: number, min = 0): boolean => {
    if (expr === "*") return true;
    if (expr.startsWith("*/")) {
      const step = Number(expr.slice(2));
      return step > 0 && (val - min) % step === 0;
    }
    return expr.split(",").some((seg) => {
      if (seg.includes("-")) {
        const [a, b] = seg.split("-").map(Number);
        return (
          typeof a === "number" &&
          typeof b === "number" &&
          val >= a &&
          val <= b
        );
      }
      return Number(seg) === val;
    });
  };

  const cursor = new Date(now);
  cursor.setSeconds(0, 0);
  cursor.setMinutes(cursor.getMinutes() + 1);

  // Caps protectores — no escaneamos más de ~366 días.
  const maxIter = 366 * 24 * 60;
  let iter = 0;
  while (out.length < count && iter < maxIter) {
    iter += 1;
    const m = cursor.getMinutes();
    const h = cursor.getHours();
    const dom = cursor.getDate();
    const mon = cursor.getMonth() + 1;
    const dow = cursor.getDay();
    if (
      inSet(m, minPart!, 59) &&
      inSet(h, hourPart!, 23) &&
      inSet(dom, domPart!, 31, 1) &&
      inSet(mon, monPart!, 12, 1) &&
      inSet(dow, dowPart!, 6)
    ) {
      out.push(new Date(cursor));
    }
    cursor.setMinutes(cursor.getMinutes() + 1);
  }
  return out;
}
