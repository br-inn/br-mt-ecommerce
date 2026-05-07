"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  DATASHEETS_NON_TERMINAL,
  importsDatasheetsApi,
  type DatasheetSummary,
  type DatasheetsRun,
} from "@/lib/api/endpoints/imports-datasheets";

export const datasheetsKeys = {
  all: () => ["imports", "datasheets"] as const,
  run: (id: string) => [...datasheetsKeys.all(), "run", id] as const,
  bySku: (sku: string) => [...datasheetsKeys.all(), "by-sku", sku] as const,
};

export function useUploadDatasheet() {
  return useMutation<
    DatasheetsRun,
    Error,
    { file: File; sku?: string | undefined }
  >({
    mutationFn: ({ file, sku }) => importsDatasheetsApi.preview(file, sku),
  });
}

export function useApplyDatasheet() {
  const qc = useQueryClient();
  return useMutation<DatasheetsRun, Error, string>({
    mutationFn: (runId) => importsDatasheetsApi.apply(runId),
    onSuccess: (run) => {
      qc.setQueryData(datasheetsKeys.run(run.run_id), run);
      // Invalida cualquier listado por SKU; los componentes se re-fetchearán
      void qc.invalidateQueries({ queryKey: datasheetsKeys.all() });
    },
  });
}

export function useDatasheetsRunStatus(
  runId: string | undefined,
  enabled = true,
) {
  return useQuery<DatasheetsRun, Error>({
    queryKey: datasheetsKeys.run(runId ?? ""),
    queryFn: () => importsDatasheetsApi.status(runId as string),
    enabled: enabled && !!runId,
    refetchInterval: (q) => {
      const data = q.state.data as DatasheetsRun | undefined;
      if (!data) return 2000;
      return DATASHEETS_NON_TERMINAL.has(data.status) ? 2000 : false;
    },
    staleTime: 0,
  });
}

export function useDatasheetsForSku(sku: string | undefined, enabled = true) {
  return useQuery<DatasheetSummary[], Error>({
    queryKey: datasheetsKeys.bySku(sku ?? ""),
    queryFn: () => importsDatasheetsApi.listForSku(sku as string),
    enabled: enabled && !!sku,
    staleTime: 60_000,
  });
}
