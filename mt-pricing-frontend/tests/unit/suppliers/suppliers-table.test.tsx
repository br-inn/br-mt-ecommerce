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
vi.mock("@/app/(app)/suppliers/_components/suppliers-filters", () => ({
  useSuppliersListFilters: () => useFiltersMock(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/suppliers",
}));

vi.mock("@/lib/hooks/use-permissions", () => ({
  usePermissions: () => ({
    hasPermissions: () => true,
    hasAnyPermission: () => true,
  }),
}));

import {
  suppliersApi,
  type SupplierListResponse,
} from "@/lib/api/endpoints/suppliers";
import { SuppliersTable } from "@/app/(app)/suppliers/_components/suppliers-table";

const messages = {
  suppliers: {
    title: "Proveedores",
    subtitle: "—",
    search: "Buscar",
    loadMore: "Cargar más",
    totalCount:
      "{count, plural, =0 {Sin proveedores} =1 {1 proveedor} other {# proveedores}}",
    daysShort: "{count, plural, =1 {1 día} other {# días}}",
    columns: {
      code: "Código",
      name: "Nombre",
      country: "País",
      currency: "Moneda",
      leadTime: "Lead time",
      email: "Email",
      active: "Activo",
      actions: "Acciones",
    },
    filters: { active: "Activos", inactive: "Inactivos" },
    empty: { title: "Sin proveedores", description: "—" },
    errors: { loadFailed: "No se pudieron cargar." },
    actions: {
      view: "Ver",
      edit: "Editar",
      activate: "Activar",
      deactivate: "Desactivar",
      deactivateConfirm: "Confirmar?",
      menu: "Acciones",
      activated: "Activado.",
      deactivated: "Desactivado.",
    },
  },
  common: {
    retry: "Reintentar",
    loading: "Cargando…",
    cancel: "Cancelar",
    confirm: "Confirmar",
    error: "Error",
  },
};

function renderTable() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <SuppliersTable />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

const sample: SupplierListResponse = {
  items: [
    {
      code: "MT_VALVES_ES",
      name: "MT Valves Iberia",
      contract_currency: "EUR",
      lead_time_days: 45,
      contact_email: "ops@mtvalves.es",
      contact_phone: null,
      payment_terms: null,
      notes: null,
      active: true,
      created_at: "2026-04-01T00:00:00Z",
      updated_at: "2026-04-01T00:00:00Z",
    },
    {
      code: "ACME_DUBAI",
      name: "ACME Dubai LLC",
      contract_currency: "AED",
      lead_time_days: 30,
      contact_email: null,
      contact_phone: null,
      payment_terms: null,
      notes: null,
      active: false,
      created_at: "2026-04-02T00:00:00Z",
      updated_at: "2026-04-02T00:00:00Z",
    },
  ],
  cursor: { next: null, prev: null },
  page_size: 25,
  total: 2,
};

describe("SuppliersTable (smoke)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFiltersMock.mockReturnValue({
      filters: {
        search: undefined,
        contract_currency: undefined,
        active: undefined,
      },
    });
  });

  it("renderiza filas con código, name, currency y badge activo", async () => {
    vi.spyOn(suppliersApi, "list").mockResolvedValue(sample);
    renderTable();
    await waitFor(() => {
      expect(screen.getByTestId("supplier-row-MT_VALVES_ES")).toBeInTheDocument();
    });
    expect(screen.getByText("MT Valves Iberia")).toBeInTheDocument();
    expect(screen.getByText("ACME Dubai LLC")).toBeInTheDocument();
  });

  it("muestra empty state cuando no hay items", async () => {
    vi.spyOn(suppliersApi, "list").mockResolvedValue({
      items: [],
      cursor: { next: null, prev: null },
      page_size: 25,
      total: 0,
    });
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("suppliers-empty")).toBeInTheDocument(),
    );
  });

  it("muestra estado de error con CTA reintentar", async () => {
    vi.spyOn(suppliersApi, "list").mockRejectedValue(new Error("network"));
    renderTable();
    await waitFor(() =>
      expect(screen.getByTestId("suppliers-error")).toBeInTheDocument(),
    );
  });
});
