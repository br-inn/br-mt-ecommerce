"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import {
  auditQueryApi,
  type AuditEvent,
  type AuditEventsPage,
  type AuditQueryFilters,
} from "@/lib/api/endpoints/audit-query";

export const auditQueryKeys = {
  all: () => ["audit-query"] as const,
  events: (filters: AuditQueryFilters) =>
    [...auditQueryKeys.all(), "events", filters] as const,
};

/**
 * Infinite query con filtros multi-entidad (S4 endpoint `/audit-events`).
 *
 * Reusa el shape `AuditEventsPage` del cliente S1.5 — backend mantiene
 * cursor opaco base64 + page_size.
 */
export function useAuditEventsQuery(filters: AuditQueryFilters) {
  return useInfiniteQuery<
    AuditEventsPage,
    Error,
    { pages: AuditEventsPage[]; pageParams: (string | null)[] },
    ReturnType<typeof auditQueryKeys.events>,
    string | null
  >({
    queryKey: auditQueryKeys.events(filters),
    queryFn: ({ pageParam }) =>
      auditQueryApi.listEvents({
        ...filters,
        cursor: pageParam,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor.next ?? undefined,
    staleTime: 30_000,
  });
}

export function flattenAuditEvents(
  data: { pages: AuditEventsPage[] } | undefined,
): AuditEvent[] {
  if (!data) return [];
  return data.pages.flatMap((p) => p.items);
}
