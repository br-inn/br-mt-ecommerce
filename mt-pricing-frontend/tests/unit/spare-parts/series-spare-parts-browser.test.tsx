import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

vi.mock("@/lib/env", () => ({
  default: {
    NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
    NEXT_PUBLIC_SUPABASE_KEY: "anon-test",
    NEXT_PUBLIC_BACKEND_URL: "http://localhost:8000",
  },
}));
vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  }),
}));

const useSparePartsMock = vi.fn();
vi.mock("@/lib/hooks/use-spare-parts", () => ({
  useSparePartsForSeries: (...args: unknown[]) => useSparePartsMock(...args),
}));

import { SeriesSparePartsBrowser } from "@/components/domain/series-spare-parts-browser";
import type { ProductCompatibility } from "@/lib/api/endpoints/products";

function makeRow(overrides: Partial<ProductCompatibility> & { id: string }): ProductCompatibility {
  return {
    id: overrides.id,
    product_sku: overrides.product_sku ?? "SRC-001",
    compatible_with_sku: overrides.compatible_with_sku ?? "PART-001",
    kind: overrides.kind ?? "spare_part",
    notes: overrides.notes ?? null,
    position: overrides.position ?? 0,
    owner_type: overrides.owner_type ?? "series",
    dn_min: overrides.dn_min ?? null,
    dn_max: overrides.dn_max ?? null,
    created_at: "2026-05-11T00:00:00Z",
    created_by: null,
    compatible_product: overrides.compatible_product ?? {
      sku: overrides.compatible_with_sku ?? "PART-001",
      display_name: "Spare Part 1",
      family: "valves",
      primary_image_url: null,
    },
  };
}

function renderBrowser(seriesId = "pn40_platinum") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SeriesSparePartsBrowser seriesId={seriesId} />
    </QueryClientProvider>,
  );
}

describe("SeriesSparePartsBrowser (Fase 5)", () => {
  beforeEach(() => {
    useSparePartsMock.mockReset();
  });

  it("muestra skeleton mientras isLoading=true", () => {
    useSparePartsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    renderBrowser();
    expect(screen.getByTestId("spare-parts-loading")).toBeInTheDocument();
  });

  it("muestra empty cuando no hay recambios", () => {
    useSparePartsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    renderBrowser();
    expect(screen.getByTestId("spare-parts-empty")).toBeInTheDocument();
  });

  it("renderiza una fila por recambio con badge de rango DN", () => {
    useSparePartsMock.mockReturnValue({
      data: [
        makeRow({ id: "1", compatible_with_sku: "PART-A", dn_min: 15, dn_max: 50 }),
        makeRow({ id: "2", compatible_with_sku: "PART-B", dn_min: null, dn_max: null }),
      ],
      isLoading: false,
      isError: false,
    });
    renderBrowser();
    expect(screen.getByTestId("spare-part-PART-A")).toBeInTheDocument();
    expect(screen.getByTestId("spare-part-PART-B")).toBeInTheDocument();
    expect(screen.getByText("DN 15–50")).toBeInTheDocument();
    // Sin rango -> placeholder "—"
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("cambiar el input de DN re-invoca el hook con el nuevo dn parseado", () => {
    useSparePartsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    renderBrowser("series-x");
    const input = screen.getByLabelText("Filtrar por DN") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "25" } });
    const lastCall = useSparePartsMock.mock.calls.at(-1);
    // Args: (seriesId, dn, enabled?)
    expect(lastCall?.[0]).toBe("series-x");
    expect(lastCall?.[1]).toBe(25);
  });

  it("input vacío deja dn como undefined", () => {
    useSparePartsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    renderBrowser("series-x");
    const lastCall = useSparePartsMock.mock.calls.at(-1);
    expect(lastCall?.[1]).toBeUndefined();
  });

  it("muestra rango unilateral '>=' cuando sólo hay dn_min", () => {
    useSparePartsMock.mockReturnValue({
      data: [makeRow({ id: "u1", dn_min: 80, dn_max: null })],
      isLoading: false,
      isError: false,
    });
    renderBrowser();
    expect(screen.getByText("DN ≥ 80")).toBeInTheDocument();
  });
});
