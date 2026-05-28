"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type PricingParamsResponse,
  type TradeRouteParamsUpdate,
  type ChannelFeeParamsUpdate,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Query keys ──────────────────────────────────────────────────────────────

export const pricingParamsKeys = {
  params: (channelCode: string) =>
    ["pricing-desk", "params", channelCode] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function usePricingParams(channelCode: string) {
  return useQuery<PricingParamsResponse, Error>({
    queryKey: pricingParamsKeys.params(channelCode),
    queryFn: () => pricingDeskApi.getParams(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

/**
 * Optimistic-update mutation for route or fee params.
 *
 * Without optimistic updates, each NumericStepper click waits for the network
 * round-trip before the value prop changes. Successive clicks all compute the
 * same `next` value (current + step) from the same stale `value` — so the
 * stepper appears frozen until the first response arrives.
 *
 * `patchKey` chooses which sub-object of PricingParamsResponse to mutate.
 */
function patchPricingParamsCache(
  prev: PricingParamsResponse | undefined,
  patchKey: "route" | "fees",
  body: Partial<TradeRouteParamsUpdate | ChannelFeeParamsUpdate>,
): PricingParamsResponse | undefined {
  if (!prev) return prev;
  const target = prev[patchKey] as Record<string, unknown>;
  return {
    ...prev,
    [patchKey]: { ...target, ...body },
  } as PricingParamsResponse;
}

export function useUpdateRouteParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<
    unknown,
    Error,
    Partial<TradeRouteParamsUpdate>,
    { previous: Array<[readonly unknown[], unknown]> }
  >({
    mutationFn: (body) =>
      pricingDeskApi.updateRouteParams(channelCode, body) as Promise<unknown>,
    onMutate: async (body) => {
      await queryClient.cancelQueries({
        queryKey: pricingParamsKeys.params(channelCode),
      });
      const previous = queryClient.getQueriesData<unknown>({
        queryKey: pricingParamsKeys.params(channelCode),
      }) as Array<[readonly unknown[], unknown]>;
      queryClient.setQueriesData<PricingParamsResponse | undefined>(
        { queryKey: pricingParamsKeys.params(channelCode) },
        (old) => patchPricingParamsCache(old, "route", body),
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
        queryKey: pricingParamsKeys.params(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useUpdateFeeParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<
    unknown,
    Error,
    Partial<ChannelFeeParamsUpdate>,
    { previous: Array<[readonly unknown[], unknown]> }
  >({
    mutationFn: (body) =>
      pricingDeskApi.updateFeeParams(channelCode, body) as Promise<unknown>,
    onMutate: async (body) => {
      await queryClient.cancelQueries({
        queryKey: pricingParamsKeys.params(channelCode),
      });
      const previous = queryClient.getQueriesData<unknown>({
        queryKey: pricingParamsKeys.params(channelCode),
      }) as Array<[readonly unknown[], unknown]>;
      queryClient.setQueriesData<PricingParamsResponse | undefined>(
        { queryKey: pricingParamsKeys.params(channelCode) },
        (old) => patchPricingParamsCache(old, "fees", body),
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
        queryKey: pricingParamsKeys.params(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}
