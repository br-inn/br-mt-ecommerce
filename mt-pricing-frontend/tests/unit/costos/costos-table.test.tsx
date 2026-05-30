import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";

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

const useFiltersMock = vi.fn();
vi.mock("@/app/(app)/costos/_components/costos-filters", () => ({
  useCostosListFilters: () => useFiltersMock(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/costos",
}));

import {
  costsApi,
  type CostsListResponse,
} from "@/lib/api/endpoints/costs";
import { CostosTable } from "@/app/(app)/costos/_components/costos-table";

const messages = {
  costos: {
    search: "Buscar por SKU",
    loadMore: "Cargar más",
    totalCount:
      "{count, plural, =0 {Sin costes} =1 {1 coste} other {# costes}}",
    columns: {
      sku: "SKU",
      scheme: "Esquema",
      supplier: "Proveedor",
      validFrom: "Desde",
      validTo: "Hasta",
      landed: "Landed AED",
      state: "Estado",
    },
    open: "abierto",
    states: { vigente: "Vigente", programado: "Programado", caducado: "Caducado" },
    empty: { title: "Sin costes", description: "—" },
    errors: { loadFailed: "No se pudieron cargar." },
  },
};

function renderTable() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <CostosTable />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

// `valid_from` muy antiguo + `valid_to` null → estado "vigente" respecto a hoy.
const sample: CostsListResponse = {
  items: [
    {
      id: "cost-1",
      sku: "MT-VAL-001",
      scheme_code: "FBA",
      supplier_code: "ACME_DUBAI",
      currency_origin: "EUR",
      fx_rate_id: null,
      breakdown: {},
      scheme_landed_aed: "123.45",
      valid_from: "2020-01-01",
      valid_to: null,
      status: "active",
      fx_inferred: false,
      version: 1,
      created_by: null,
      updated_by: null,
      created_at: "2020-01-01T00:00:00Z",
      updated_at: "2020-01-01T00:00:00Z",
    },
  ],
  cursor: { next: null, prev: null },
  page_size: 50,
  total: 1,
};

describe("CostosTable (smoke)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFiltersMock.mockReturnValue({
      filters: {
        sku: undefined,
        scheme: undefined,
        supplier: undefined,
        valid_on: undefined,
        include_history: undefined,
      },
    });
  });

  it("renderiza filas con sku, scheme, valid_from y badge de estado", async () => {
    vi.spyOn(costsApi, "list").mockResolvedValue(sample);
    renderTable();
    await waitFor(() => {
      expect(screen.getByTestId("costo-row-cost-1")).toBeInTheDocument();
    });
    expect(screen.getByText("MT-VAL-001")).toBeInTheDocument();
    expect(screen.getByText("FBA")).toBeInTheDocument();
    // valid_from 2020-01-01 → estado "Vigente"
    expect(screen.getByText("Vigente")).toBeInTheDocument();
    expect(screen.getByTestId("costos-table-root")).toBeInTheDocument();
  });

  it("muestra empty state cuando no hay items", async () => {
    vi.spyOn(costsApi, "list").mockResolvedValue({
      items: [],
      cursor: { next: null, prev: null },
      page_size: 50,
      total: 0,
    });
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("costos-empty")).toBeInTheDocument(),
    );
  });

  it("muestra estado de error", async () => {
    vi.spyOn(costsApi, "list").mockRejectedValue(new Error("network"));
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("costos-error")).toBeInTheDocument(),
    );
  });
});
