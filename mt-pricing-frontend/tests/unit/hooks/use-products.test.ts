import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { useProducts } from "@/lib/hooks/products/use-products";
import { productKeys } from "@/lib/hooks/products/query-keys";
import { productsApi, type ProductListResponse } from "@/lib/api/endpoints/products";

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

const baseResponse: ProductListResponse = {
  items: [
    {
      internal_id: "00000000-0000-0000-0000-000000000001",
      sku: "VAL-001",
      family: "valves",
      family_id: null,
      subfamily: null,
      dn: "DN50",
      pn: "PN16",
      material: "steel",
      type: null,
      data_quality: "complete",
      translation_status_es: "approved",
      translation_status_ar: null,
      active: true,
      lifecycle_status: "active",
      primary_image_url: null,
      updated_at: "2026-05-06T12:00:00Z",
      series_id: null,
      material_id: null,
      display_pair_sku: null,
      division_codes: [],
      translations: { en: { name: "Valve" } },
    },
  ],
  next_cursor: null,
  total: 1,
  page_size: 25,
  page: 1,
  pages: 1,
};

describe("useProducts", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls productsApi.list with the supplied filters and exposes data directly", async () => {
    const spy = vi.spyOn(productsApi, "list").mockResolvedValue(baseResponse);

    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useProducts({ family: "valves", active: true, page: 1 }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ family: "valves", active: true, page: 1 }),
    );
    // Data is now direct (not nested under .pages[])
    expect(result.current.data?.items[0]?.sku).toBe("VAL-001");
    expect(result.current.data?.page).toBe(1);
    expect(result.current.data?.pages).toBe(1);
  });

  it("uses a stable queryKey derived from filters", () => {
    const key = productKeys.list({ family: "fittings", page: 2 });
    expect(key).toEqual(["products", "list", { family: "fittings", page: 2 }]);
  });
});
