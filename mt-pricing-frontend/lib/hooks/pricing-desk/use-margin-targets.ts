"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type MarginTarget,
  type MarginTargetUpsert,
  type MarginOverrideRead,
  type MarginOverrideUpsert,
  type SellingModel,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Query keys ──────────────────────────────────────────────────────────────

export const marginTargetKeys = {
  targets: (channelCode: string) =>
    ["pricing-desk", "margin-targets", channelCode] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useMarginTargets(channelCode: string) {
  return useQuery<MarginTarget[], Error>({
    queryKey: marginTargetKeys.targets(channelCode),
    queryFn: () => pricingDeskApi.listMarginTargets(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useUpsertMarginTarget(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<
    void,
    Error,
    MarginTargetUpsert,
    { previous: Array<[readonly unknown[], unknown]> }
  >({
    mutationFn: (body) => pricingDeskApi.upsertMarginTarget(channelCode, body),
    onMutate: async (body) => {
      // Cancel in-flight queries that we are about to overwrite
      await queryClient.cancelQueries({
        queryKey: marginTargetKeys.targets(channelCode),
      });
      const previous = queryClient.getQueriesData<unknown>({
        queryKey: marginTargetKeys.targets(channelCode),
      }) as Array<[readonly unknown[], unknown]>;
      // Optimistically update the matching family target so the stepper
      // reflects the new value immediately. Without this, the NumericStepper's
      // value prop stays at the old value during the network round-trip and
      // successive clicks send the same +1 from the same base — UX is broken.
      queryClient.setQueriesData<MarginTarget[] | undefined>(
        { queryKey: marginTargetKeys.targets(channelCode) },
        (old) => {
          if (!Array.isArray(old)) return old;
          return old.map((t) =>
            t.family_id === body.family_id &&
            t.selling_model === body.selling_model
              ? { ...t, margin_target_pct: String(body.margin_target_pct) }
              : t,
          );
        },
      );
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) {
        for (const [key, data] of ctx.previous) {
          queryClient.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: marginTargetKeys.targets(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useUpsertMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<
    MarginOverrideRead,
    Error,
    { sku: string; body: MarginOverrideUpsert },
    { previous: Array<[readonly unknown[], unknown]> }
  >({
    mutationFn: ({ sku, body }) =>
      pricingDeskApi.upsertMarginOverride(channelCode, sku, body),
    onMutate: async ({ sku, body }) => {
      // Cancel in-flight refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
      // Snapshot previous cache for rollback on error
      const previous = queryClient.getQueriesData<unknown>({
        queryKey: ["pricing-desk", "catalog", channelCode],
      }) as Array<[readonly unknown[], unknown]>;
      // Optimistically update margin_pct in every cached catalog slice
      queryClient.setQueriesData<unknown>(
        { queryKey: ["pricing-desk", "catalog", channelCode] },
        (old: unknown) => {
          if (
            !old ||
            typeof old !== "object" ||
            !("rows" in old) ||
            !Array.isArray((old as { rows: unknown }).rows)
          ) {
            return old;
          }
          const data = old as {
            rows: Array<Record<string, unknown>>;
          } & Record<string, unknown>;
          return {
            ...data,
            rows: data.rows.map((r) =>
              r.sku === sku
                ? { ...r, margin_pct: Number(body.margin_override_pct) }
                : r,
            ),
          };
        },
      );
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      // Roll back optimistic update on failure
      if (ctx?.previous) {
        for (const [key, data] of ctx.previous) {
          queryClient.setQueryData(key, data);
        }
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useDeleteMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { sku: string; sellingModel: SellingModel }>({
    mutationFn: ({ sku, sellingModel }) =>
      pricingDeskApi.deleteMarginOverride(channelCode, sku, sellingModel),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}
