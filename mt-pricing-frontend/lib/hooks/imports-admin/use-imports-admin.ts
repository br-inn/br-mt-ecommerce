"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  TERMINAL_RUN_STATUSES,
  importsAdminApi,
  type ImportRunRow,
  type ImportRunStatus,
  type ImportRunsPage,
  type ImportType,
  type RunFromFixtureResponse,
  type UploadResponse,
} from "@/lib/api/endpoints/imports-admin";

export const importsAdminKeys = {
  all: () => ["imports-admin"] as const,
  list: (params: {
    import_type?: ImportType | undefined;
    status?: ImportRunStatus | undefined;
  }) => [...importsAdminKeys.all(), "list", params] as const,
  detail: (id: string) => [...importsAdminKeys.all(), "detail", id] as const,
};

export function useImportRunsList(
  params: {
    import_type?: ImportType | undefined;
    status?: ImportRunStatus | undefined;
    limit?: number | undefined;
  } = {},
) {
  return useQuery<ImportRunsPage, Error>({
    queryKey: importsAdminKeys.list({
      ...(params.import_type !== undefined ? { import_type: params.import_type } : {}),
      ...(params.status !== undefined ? { status: params.status } : {}),
    }),
    queryFn: () => importsAdminApi.listRuns(params),
    staleTime: 10_000,
    refetchInterval: 5000,
  });
}

export function useImportRunDetail(runId: string | undefined) {
  return useQuery<ImportRunRow, Error>({
    queryKey: importsAdminKeys.detail(runId ?? ""),
    queryFn: () => importsAdminApi.getRun(runId as string),
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as ImportRunRow | undefined;
      if (!data) return 3000;
      return TERMINAL_RUN_STATUSES.has(data.status) ? false : 3000;
    },
    staleTime: 0,
  });
}

export function useUploadPim() {
  const qc = useQueryClient();
  return useMutation<UploadResponse, Error, { file: File }>({
    mutationFn: ({ file }) => importsAdminApi.uploadPim(file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: importsAdminKeys.all() });
    },
  });
}

export function useRunFromFixture() {
  const qc = useQueryClient();
  return useMutation<RunFromFixtureResponse, Error, void>({
    mutationFn: () => importsAdminApi.runFromFixture(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: importsAdminKeys.all() });
    },
  });
}
