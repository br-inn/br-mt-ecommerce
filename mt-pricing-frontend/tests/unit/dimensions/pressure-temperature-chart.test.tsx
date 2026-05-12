import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

import { dimensionsApi } from "@/lib/api/endpoints/dimensions";
import {
  PressureTemperatureChart,
  computeRanges,
  groupBySeries,
} from "@/components/domain/pressure-temperature-chart";
import type { PressureTemperaturePoint } from "@/lib/api/types-dimensions";

const SKU = "MT-V-001";

function makePoint(
  over: Partial<PressureTemperaturePoint>,
): PressureTemperaturePoint {
  return {
    id: "p-1",
    product_sku: SKU,
    series_variant_code: null,
    temperature_c: 0,
    pressure_max_bar: 10,
    condition_en: null,
    order_index: 0,
    ...over,
  };
}

function renderChart() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    React.createElement(
      QueryClientProvider,
      { client },
      React.createElement(PressureTemperatureChart, { sku: SKU }),
    ),
  );
}

describe("PressureTemperatureChart — helpers", () => {
  it("groupBySeries buckets and sorts by ascending temperature", () => {
    const groups = groupBySeries([
      makePoint({ id: "a", series_variant_code: "A", temperature_c: 50 }),
      makePoint({ id: "b", series_variant_code: "A", temperature_c: 20 }),
      makePoint({ id: "c", series_variant_code: "B", temperature_c: 0 }),
    ]);
    expect(Array.from(groups.keys()).sort()).toEqual(["A", "B"]);
    expect(groups.get("A")!.map((p) => p.id)).toEqual(["b", "a"]);
  });

  it("computeRanges returns null on empty input and pads otherwise", () => {
    expect(computeRanges([])).toBeNull();
    const r = computeRanges([
      makePoint({ temperature_c: 10, pressure_max_bar: 10 }),
      makePoint({ temperature_c: 100, pressure_max_bar: 50 }),
    ])!;
    expect(r.minT).toBeLessThan(10);
    expect(r.maxT).toBeGreaterThan(100);
    expect(r.minP).toBeGreaterThanOrEqual(0);
    expect(r.maxP).toBeGreaterThan(50);
  });
});

describe("PressureTemperatureChart — render", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the placeholder when there are no points", async () => {
    vi.spyOn(
      dimensionsApi,
      "getProductPressureTemperature",
    ).mockResolvedValue({
      product_sku: SKU,
      series_variant_code: null,
      points: [],
    });

    renderChart();

    await waitFor(() =>
      expect(screen.getByText(/Sin curva P-T disponible/i)).toBeInTheDocument(),
    );
  });

  it("renders an SVG with one marker per point when data is present", async () => {
    vi.spyOn(
      dimensionsApi,
      "getProductPressureTemperature",
    ).mockResolvedValue({
      product_sku: SKU,
      series_variant_code: null,
      points: [
        makePoint({
          id: "p-1",
          temperature_c: 20,
          pressure_max_bar: 16,
        }),
        makePoint({
          id: "p-2",
          temperature_c: 100,
          pressure_max_bar: 10,
        }),
      ],
    });

    renderChart();

    await waitFor(() => {
      expect(
        screen.getByRole("img", { name: /pressure-temperature curve/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("pt-marker-p-1")).toBeInTheDocument();
    expect(screen.getByTestId("pt-marker-p-2")).toBeInTheDocument();
  });

  it("renders a legend when multiple series_variant_code values are present", async () => {
    vi.spyOn(
      dimensionsApi,
      "getProductPressureTemperature",
    ).mockResolvedValue({
      product_sku: SKU,
      series_variant_code: null,
      points: [
        makePoint({
          id: "p-1",
          series_variant_code: "STD",
          temperature_c: 20,
          pressure_max_bar: 16,
        }),
        makePoint({
          id: "p-2",
          series_variant_code: "HT",
          temperature_c: 200,
          pressure_max_bar: 10,
        }),
        makePoint({
          id: "p-3",
          series_variant_code: "HT",
          temperature_c: 100,
          pressure_max_bar: 14,
        }),
      ],
    });

    renderChart();

    const legend = await screen.findByTestId("pt-legend");
    expect(legend).toBeInTheDocument();
    expect(legend.textContent).toMatch(/STD/);
    expect(legend.textContent).toMatch(/HT/);
  });
});
