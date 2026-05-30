import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import {
  useCreateCost,
  useCostAsOf,
  useCloseCost,
} from "@/lib/hooks/costs/use-costs";
import {
  costsApi,
  type Cost,
  type CostCreatedResponse,
} from "@/lib/api/endpoints/costs";

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    Wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client }, children),
  };
}

const COST: Cost = {
  id: "00000000-0000-0000-0000-000000000001",
  sku: "SKU-1",
  scheme_code: "FBA",
  supplier_code: null,
  currency_origin: "AED",
  fx_rate_id: null,
  breakdown: { fob: 10 },
  scheme_landed_aed: "10.00",
  valid_from: "2026-01-01",
  valid_to: null,
  status: "active",
  fx_inferred: false,
  version: 1,
  created_by: null,
  updated_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  // legacy aliases (read-only)
  product_sku: "SKU-1",
  total: "10.00",
  currency: "AED",
};

const CREATED: CostCreatedResponse = { cost: COST, warnings: [] };

describe("useCreateCost", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls costsApi.create with a valid_from field (not effective_at)", async () => {
    const spy = vi.spyOn(costsApi, "create").mockResolvedValue(CREATED);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useCreateCost(), { wrapper: Wrapper });

    await result.current.mutateAsync({
      sku: "SKU-1",
      scheme_code: "FBA",
      currency_origin: "AED",
      breakdown: { fob: 10 },
      valid_from: "2026-01-01",
    });

    expect(spy).toHaveBeenCalledTimes(1);
    const arg = spy.mock.calls[0]?.[0] as unknown as Record<string, unknown>;
    expect(arg["valid_from"]).toBe("2026-01-01");
    expect(arg).not.toHaveProperty("effective_at");
  });
});

describe("useCostAsOf", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls costsApi.asOf with the given params", async () => {
    const spy = vi.spyOn(costsApi, "asOf").mockResolvedValue(COST);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useCostAsOf({
          sku: "SKU-1",
          scheme_code: "FBA",
          date: "2026-03-01",
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({
      sku: "SKU-1",
      scheme_code: "FBA",
      date: "2026-03-01",
    });
    expect(result.current.data?.id).toBe(COST.id);
  });

  it("is disabled when params are incomplete", () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useCostAsOf({ sku: "", scheme_code: "FBA", date: "2026-03-01" }),
      { wrapper: Wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useCloseCost", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls costsApi.close with id and valid_to, then invalidates", async () => {
    const spy = vi.spyOn(costsApi, "close").mockResolvedValue(COST);
    const { Wrapper, client } = createWrapper();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCloseCost(), { wrapper: Wrapper });

    await result.current.mutateAsync({
      id: COST.id,
      valid_to: "2026-06-30",
    });

    expect(spy).toHaveBeenCalledWith(COST.id, "2026-06-30");
    expect(invalidate).toHaveBeenCalled();
  });
});
