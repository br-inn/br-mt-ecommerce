"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  COSTS_NON_TERMINAL,
  importsCostsApi,
  type ImportCostsPreview,
  type ImportCostsRun,
} from "@/lib/api/endpoints/imports-costs";

export const importCostsKeys = {
  all: () => ["imports", "costs"] as const,
  details: () => [...importCostsKeys.all(), "detail"] as const,
  detail: (id: string) => [...importCostsKeys.details(), id] as const,
  status: (id: string) => [...importCostsKeys.detail(id), "status"] as const,
};

export function useUploadCostsImport() {
  return useMutation<ImportCostsPreview, Error, { file: File }>({
    mutationFn: ({ file }) => importsCostsApi.preview(file),
  });
}

export function useApplyCostsImport() {
  const qc = useQueryClient();
  return useMutation<ImportCostsRun, Error, string>({
    mutationFn: (runId) => importsCostsApi.apply(runId),
    onSuccess: (run) => {
      qc.setQueryData(importCostsKeys.status(run.run_id), run);
    },
  });
}

export function useCostsImportStatus(runId: string | undefined, enabled = true) {
  return useQuery<ImportCostsRun, Error>({
    queryKey: importCostsKeys.status(runId ?? ""),
    queryFn: () => importsCostsApi.status(runId as string),
    enabled: enabled && !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as ImportCostsRun | undefined;
      if (!data) return 2000;
      return COSTS_NON_TERMINAL.has(data.status) ? 2000 : false;
    },
    staleTime: 0,
  });
}
