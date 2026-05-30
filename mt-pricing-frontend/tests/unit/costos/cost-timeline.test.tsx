import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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

import { CostTimeline } from "@/components/domain/costs/cost-timeline";
import type { Cost } from "@/lib/api/endpoints/costs";

function makeCost(over: Partial<Cost>): Cost {
  return {
    id: over.id ?? "00000000-0000-0000-0000-000000000000",
    sku: "SKU-1",
    scheme_code: "FBA",
    supplier_code: "ACME_DUBAI",
    currency_origin: "USD",
    fx_rate_id: null,
    breakdown: {},
    scheme_landed_aed: "1000.00",
    effective_at: "2026-01-01T00:00:00Z",
    status: "active",
    fx_inferred: false,
    version: 1,
    created_by: null,
    updated_by: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    product_sku: "SKU-1",
    total: "1000.00",
    currency: "AED",
    fx_at: null,
    valid_from: "2026-01-01",
    valid_to: null,
    ...over,
  };
}

describe("CostTimeline", () => {
  beforeAll(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-15"));
  });
  afterAll(() => {
    vi.useRealTimers();
  });

  it("renderiza los 3 rangos con sus badges y el rango abierto como 'abierto'", () => {
    const caducado = makeCost({
      id: "c-caducado",
      valid_from: "2026-01-01",
      valid_to: "2026-03-31",
      scheme_landed_aed: "980.00",
    });
    const vigente = makeCost({
      id: "c-vigente",
      valid_from: "2026-04-01",
      valid_to: null, // abierto
      scheme_landed_aed: "1310.00",
    });
    const programado = makeCost({
      id: "c-programado",
      valid_from: "2026-09-01",
      valid_to: null,
      scheme_landed_aed: "1450.00",
    });

    // Pasamos en orden desordenado para verificar el sort ascendente.
    render(<CostTimeline costs={[programado, vigente, caducado]} />);

    // Una fila por rango.
    expect(screen.getByTestId("cost-range-c-caducado")).toBeInTheDocument();
    expect(screen.getByTestId("cost-range-c-vigente")).toBeInTheDocument();
    expect(screen.getByTestId("cost-range-c-programado")).toBeInTheDocument();

    // Badges de estado.
    expect(screen.getByText("Caducado")).toBeInTheDocument();
    expect(screen.getByText("Vigente")).toBeInTheDocument();
    expect(screen.getByText("Programado")).toBeInTheDocument();

    // El rango vigente es abierto (valid_to null) → muestra "(abierto)".
    const vigenteRow = screen.getByTestId("cost-range-c-vigente");
    expect(vigenteRow).toHaveTextContent(/abierto/i);

    // El importe AED del rango vigente se muestra formateado + moneda AED.
    expect(vigenteRow).toHaveTextContent("1,310.00");
    expect(vigenteRow).toHaveTextContent("AED");
  });

  it("marca visualmente la fila vigente con el atributo data-current", () => {
    const vigente = makeCost({
      id: "c-vigente",
      valid_from: "2026-04-01",
      valid_to: null,
    });
    render(<CostTimeline costs={[vigente]} />);
    const row = screen.getByTestId("cost-range-c-vigente");
    expect(row).toHaveAttribute("data-current", "true");
  });

  it("ordena los rangos por valid_from ascendente", () => {
    const a = makeCost({ id: "a", valid_from: "2026-01-01", valid_to: "2026-03-31" });
    const b = makeCost({ id: "b", valid_from: "2026-04-01", valid_to: null });
    const c = makeCost({ id: "c", valid_from: "2026-09-01", valid_to: null });
    render(<CostTimeline costs={[c, a, b]} />);
    const rows = screen.getAllByTestId(/^cost-range-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "cost-range-a",
      "cost-range-b",
      "cost-range-c",
    ]);
  });

  it("renderiza MtEmpty cuando costs está vacío", () => {
    render(<CostTimeline costs={[]} />);
    expect(screen.getByText("Sin rangos de coste")).toBeInTheDocument();
  });
});
