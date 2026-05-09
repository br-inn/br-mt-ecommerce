import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
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

const useFiltersMock = vi.fn();
vi.mock("@/app/(app)/products/_components/products-filters", () => ({
  useProductsListFilters: () => useFiltersMock(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/products",
}));

import { productsApi, type ProductListResponse } from "@/lib/api/endpoints/products";
import { ProductsTable } from "@/app/(app)/products/_components/products-table";

const baseMessages = {
  catalog: {
    title: "Catálogo",
    subtitle: "—",
    loading: "Cargando…",
    loadMore: "Cargar más",
    totalCount: "{count, plural, =0 {Sin productos} =1 {1 producto} other {# productos}}",
    columns: {
      sku: "SKU",
      name: "Nombre",
      family: "Familia",
      dn: "DN",
      pn: "PN",
      material: "Material",
      active: "Activo",
      actions: "Acciones",
      dataQuality: "Calidad",
    },
    filters: {
      active: "Activos",
      inactive: "Inactivos",
    },
    empty: { title: "Sin productos", description: "—", create: "Crear" },
    errors: {
      loadFailed: "No se pudieron cargar los productos.",
      notFound: "No encontrado",
    },
  },
  common: { retry: "Reintentar", loading: "Cargando…" },
};

function renderTable() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="es" messages={baseMessages} timeZone="UTC">
        <ProductsTable />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

const sampleResponse: ProductListResponse = {
  items: [
    {
      internal_id: "00000000-0000-0000-0000-000000000001",
      sku: "MTV-1004",
      name_en: "Ball valve PN16",
      family: "valves",
      dn: "DN25",
      pn: "PN16",
      material: "CW617N",
      type: "ball",
      data_quality: "complete",
      translation_status_es: "approved",
      translation_status_ar: null,
      active: true,
      primary_image_url: null,
      updated_at: "2026-05-06T12:00:00Z",
      series_id: null,
      material_id: null,
      display_pair_sku: null,
      division_codes: [],
    },
    {
      internal_id: "00000000-0000-0000-0000-000000000002",
      sku: "MTV-1011",
      name_en: "Gate valve PN16",
      family: "valves",
      dn: "DN50",
      pn: "PN16",
      material: "CW617N",
      type: "gate",
      data_quality: "partial",
      translation_status_es: "draft",
      translation_status_ar: null,
      active: false,
      primary_image_url: null,
      updated_at: "2026-05-05T12:00:00Z",
      series_id: null,
      material_id: null,
      display_pair_sku: null,
      division_codes: [],
    },
  ],
  next_cursor: null,
  total: 2,
  page_size: 25,
};

describe("ProductsTable (Pantalla 2)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFiltersMock.mockReturnValue({
      filters: { family: undefined, brand: undefined, search: undefined },
    });
  });

  it("renderiza filas con SKU, name, family, DN, PN, material y estado", async () => {
    vi.spyOn(productsApi, "list").mockResolvedValue(sampleResponse);
    renderTable();

    await waitFor(() => {
      expect(screen.getByTestId("product-row-MTV-1004")).toBeInTheDocument();
    });
    expect(screen.getByTestId("product-row-MTV-1011")).toBeInTheDocument();
    expect(screen.getByText("Ball valve PN16")).toBeInTheDocument();
    expect(screen.getAllByText("CW617N").length).toBeGreaterThanOrEqual(1);
  });

  it("aplica el filtro family a la query", async () => {
    useFiltersMock.mockReturnValue({
      filters: { family: "valves", brand: undefined, search: undefined },
    });
    const spy = vi.spyOn(productsApi, "list").mockResolvedValue(sampleResponse);
    renderTable();

    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ family: "valves" }),
    );
  });

  it("muestra el botón 'cargar más' cuando hay next_cursor", async () => {
    vi.spyOn(productsApi, "list").mockResolvedValue({
      ...sampleResponse,
      next_cursor: "cursor-abc",
    });
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("products-load-more")).toBeInTheDocument(),
    );
  });

  it("muestra el empty state cuando no hay items", async () => {
    vi.spyOn(productsApi, "list").mockResolvedValue({
      items: [],
      next_cursor: null,
      total: 0,
      page_size: 25,
    });
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("products-empty")).toBeInTheDocument(),
    );
  });

  it("muestra estado de error con CTA de reintentar", async () => {
    vi.spyOn(productsApi, "list").mockRejectedValue(new Error("network"));
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("products-error")).toBeInTheDocument(),
    );
  });
});
