"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NON_TERMINAL_STATUSES,
  importsApi,
  type ImportPreview,
  type ImportReport,
  type ImportRun,
} from "@/lib/api/endpoints/imports";

export const importKeys = {
  all: () => ["imports"] as const,
  details: () => [...importKeys.all(), "detail"] as const,
  detail: (id: string) => [...importKeys.details(), id] as const,
  status: (id: string) => [...importKeys.detail(id), "status"] as const,
  report: (id: string) => [...importKeys.detail(id), "report"] as const,
};

/** Mutación: subir XLSX → preview. */
export function useUploadImport() {
  return useMutation<ImportPreview, Error, { file: File }>({
    mutationFn: ({ file }) => importsApi.preview(file, "pim"),
  });
}

/** Mutación: confirmar y aplicar el run.
 *
 * Stage 3 (Wave 11): acepta `division_codes` opcional para override per-run.
 */
export interface ApplyVars {
  runId: string;
  division_codes?: string[] | null;
}

export function useApplyImport() {
  const qc = useQueryClient();
  return useMutation<ImportRun, Error, ApplyVars | string>({
    mutationFn: (vars) => {
      if (typeof vars === "string") return importsApi.apply(vars);
      const opts: { division_codes?: string[] | null } = {};
      if (vars.division_codes !== undefined) opts.division_codes = vars.division_codes;
      return importsApi.apply(vars.runId, opts);
    },
    onSuccess: (run) => {
      qc.setQueryData(importKeys.status(run.id), run);
    },
  });
}

/**
 * Polling cada 2s mientras el status sea no-terminal.
 * Para el wizard: encender cuando entramos en step "apply", apagar cuando completed/failed.
 */
export function useImportStatus(runId: string | undefined, enabled = true) {
  return useQuery<ImportRun, Error>({
    queryKey: importKeys.status(runId ?? ""),
    queryFn: () => importsApi.status(runId as string),
    enabled: enabled && !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as ImportRun | undefined;
      if (!data) return 2000;
      return NON_TERMINAL_STATUSES.has(data.status) ? 2000 : false;
    },
    staleTime: 0,
  });
}

/** Reporte final, sólo cuando el run está en estado terminal. */
export function useImportReport(runId: string | undefined, enabled = true) {
  return useQuery<ImportReport, Error>({
    queryKey: importKeys.report(runId ?? ""),
    queryFn: () => importsApi.report(runId as string),
    enabled: enabled && !!runId,
    staleTime: 60_000,
  });
}
