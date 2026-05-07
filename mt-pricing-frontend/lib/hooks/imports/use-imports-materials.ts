"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  importsMaterialsApi,
  type ImportMaterialsApplyMode,
  type ImportMaterialsPreview,
  type ImportMaterialsRun,
} from "@/lib/api/endpoints/imports-materials";

export const importMaterialsKeys = {
  all: () => ["imports", "materials"] as const,
  details: () => [...importMaterialsKeys.all(), "detail"] as const,
  detail: (id: string) => [...importMaterialsKeys.details(), id] as const,
  status: (id: string) => [...importMaterialsKeys.detail(id), "status"] as const,
};

export function useUploadMaterialsImport() {
  return useMutation<ImportMaterialsPreview, Error, { file: File }>({
    mutationFn: ({ file }) => importsMaterialsApi.preview(file),
  });
}

export function useApplyMaterialsImport() {
  const qc = useQueryClient();
  return useMutation<
    ImportMaterialsRun,
    Error,
    { runId: string; mode?: ImportMaterialsApplyMode }
  >({
    mutationFn: ({ runId, mode = "replace" }) =>
      importsMaterialsApi.apply(runId, mode),
    onSuccess: (run) => {
      qc.setQueryData(importMaterialsKeys.status(run.run_id), run);
    },
  });
}

export function useMaterialsImportStatus(
  runId: string | undefined,
  enabled = true,
) {
  return useQuery<ImportMaterialsRun, Error>({
    queryKey: importMaterialsKeys.status(runId ?? ""),
    queryFn: () => importsMaterialsApi.status(runId as string),
    enabled: enabled && !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as ImportMaterialsRun | undefined;
      if (!data) return 2000;
      return data.status === "applying" ? 2000 : false;
    },
    staleTime: 0,
  });
}
