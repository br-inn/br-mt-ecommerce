"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import {
  auditApi,
  type AuditEvent,
  type AuditEventFilters,
  type AuditEventsPage,
} from "@/lib/api/endpoints/audit";

export const auditKeys = {
  all: () => ["audit"] as const,
  events: (filters: AuditEventFilters) =>
    [...auditKeys.all(), "events", filters] as const,
};

/**
 * Infinite query sobre audit events con cursor pagination.
 *
 * El cliente itera con `fetchNextPage` mientras `cursor.next` no sea null.
 * Cada page llega como `AuditEventsPage`; el componente UI aplana los items.
 */
export function useAuditEvents(filters: AuditEventFilters) {
  return useInfiniteQuery<
    AuditEventsPage,
    Error,
    { pages: AuditEventsPage[]; pageParams: (string | null)[] },
    ReturnType<typeof auditKeys.events>,
    string | null
  >({
    queryKey: auditKeys.events(filters),
    queryFn: ({ pageParam }) =>
      auditApi.listEvents({
        ...filters,
        cursor: pageParam,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor.next ?? undefined,
    staleTime: 30_000,
  });
}

export function flattenEvents(
  data: { pages: AuditEventsPage[] } | undefined,
): AuditEvent[] {
  if (!data) return [];
  return data.pages.flatMap((p) => p.items);
}
