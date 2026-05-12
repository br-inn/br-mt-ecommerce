"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "@/lib/api/endpoints/documents";
import type {
  Document,
  DocumentCreatePayload,
  DocumentListFilters,
  DocumentPatchPayload,
} from "@/lib/api/types-assets-extended";

const documentsKeys = {
  all: () => ["documents"] as const,
  lists: () => [...documentsKeys.all(), "list"] as const,
  list: (filters: DocumentListFilters) =>
    [...documentsKeys.lists(), filters] as const,
  details: () => [...documentsKeys.all(), "detail"] as const,
  detail: (id: string) => [...documentsKeys.details(), id] as const,
};

export function useDocuments(filters: DocumentListFilters = {}) {
  return useQuery<Document[], Error>({
    queryKey: documentsKeys.list(filters),
    queryFn: () => documentsApi.list(filters),
    staleTime: 30_000,
  });
}

export function useDocument(id: string | undefined) {
  return useQuery<Document, Error>({
    queryKey: documentsKeys.detail(id ?? ""),
    queryFn: () => documentsApi.get(id as string),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateDocument() {
  const qc = useQueryClient();
  return useMutation<Document, Error, DocumentCreatePayload>({
    mutationFn: (payload) => documentsApi.create(payload),
    onSuccess: (created) => {
      qc.setQueryData(documentsKeys.detail(created.id), created);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: documentsKeys.lists() });
    },
  });
}

export function useUpdateDocument(id: string) {
  const qc = useQueryClient();
  return useMutation<Document, Error, DocumentPatchPayload>({
    mutationFn: (payload) => documentsApi.patch(id, payload),
    onSuccess: (updated) => {
      qc.setQueryData(documentsKeys.detail(updated.id), updated);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: documentsKeys.lists() });
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => documentsApi.remove(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: documentsKeys.detail(id) });
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: documentsKeys.lists() });
    },
  });
}

export { documentsKeys };
