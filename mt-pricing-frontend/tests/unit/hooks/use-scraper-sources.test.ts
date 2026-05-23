import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import {
  useScraperSources,
  useCreateScraperSource,
  useScraperSourceRecipes,
  useValidateRecipe,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  scraperSourcesApi,
  type ScraperSourceRead,
  type RecipeRead,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    Wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client }, children),
  };
}

const SOURCE: ScraperSourceRead = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "test-source",
  slug: "test-source",
  base_url: "https://example.com",
  description: null,
  destination_profile: "competitor_price",
  fetch_mode: "static",
  status: "draft",
  competitor_brand_id: null,
  created_at: "2026-05-24T00:00:00Z",
  updated_at: "2026-05-24T00:00:00Z",
};

const RECIPE: RecipeRead = {
  id: "00000000-0000-0000-0000-000000000002",
  source_id: SOURCE.id,
  version: 1,
  is_live: false,
  validation_status: "unvalidated",
  has_unapproved_snippet: false,
  recipe: { url_templates: { search: "" }, list_item_selector: "", fields: [] },
  created_at: "2026-05-24T00:00:00Z",
};

describe("useScraperSources", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("fetches and returns the sources list", async () => {
    vi.spyOn(scraperSourcesApi, "list").mockResolvedValue([SOURCE]);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useScraperSources(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.id).toBe(SOURCE.id);
  });
});

describe("useCreateScraperSource", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls create and invalidates list query", async () => {
    vi.spyOn(scraperSourcesApi, "create").mockResolvedValue(SOURCE);
    const { Wrapper, client } = createWrapper();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScraperSource(), { wrapper: Wrapper });
    await result.current.mutateAsync({
      name: "test-source",
      slug: "test-source",
      base_url: "https://example.com",
      destination_profile: "competitor_price",
      fetch_mode: "static",
    });
    expect(invalidate).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: expect.arrayContaining(["scraper-sources"]) }),
    );
  });
});

describe("useScraperSourceRecipes", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("fetches recipes for a source", async () => {
    vi.spyOn(scraperSourcesApi, "listRecipes").mockResolvedValue([RECIPE]);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useScraperSourceRecipes(SOURCE.id),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.id).toBe(RECIPE.id);
  });

  it("is disabled when sourceId is null", () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useScraperSourceRecipes(null),
      { wrapper: Wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useValidateRecipe", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls validate with the correct sourceId", async () => {
    const response: ValidateResponse = {
      status: "passing",
      field_results: { price: "pass" },
      records: [],
    };
    const spy = vi.spyOn(scraperSourcesApi, "validate").mockResolvedValue(response);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useValidateRecipe(SOURCE.id),
      { wrapper: Wrapper },
    );
    await result.current.mutateAsync({ recipe_id: RECIPE.id, test_url: "https://example.com" });
    expect(spy).toHaveBeenCalledWith(SOURCE.id, {
      recipe_id: RECIPE.id,
      test_url: "https://example.com",
    });
  });
});
