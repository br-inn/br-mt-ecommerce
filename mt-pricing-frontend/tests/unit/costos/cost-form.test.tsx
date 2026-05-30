import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
// El sheet va envuelto en <RbacGuard permissions={["costs:write"]}> — concedemos.
vi.mock("@/lib/hooks/use-permissions", () => ({
  usePermissions: () => ({
    hasPermissions: () => true,
    hasAnyPermission: () => true,
  }),
}));

import { costsApi, type Cost } from "@/lib/api/endpoints/costs";
import { CostsTabClient } from "@/app/(app)/catalogo/[sku]/costos/_client";
import { CostTable } from "@/components/domain/costs/cost-table";

const messages = { common: { cancel: "Cancelar", loading: "…", error: "Error" } };

function renderWithProviders(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

function makeCost(overrides: Partial<Cost> = {}): Cost {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    sku: "SKU-1",
    scheme_code: "FBA",
    supplier_code: null,
    currency_origin: "EUR",
    fx_rate_id: null,
    breakdown: { fob_eur: 10 },
    scheme_landed_aed: "40.00",
    valid_from: "2026-01-01",
    valid_to: null,
    status: "active",
    fx_inferred: false,
    version: 1,
    created_by: null,
    updated_by: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("CostsTabClient — crear coste (contrato valid_from)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("envía valid_from (date string) y NO effective_at al crear", async () => {
    vi.spyOn(costsApi, "listForSku").mockResolvedValue([]);
    const createSpy = vi.spyOn(costsApi, "create").mockResolvedValue({
      cost: makeCost(),
      warnings: [],
    });

    renderWithProviders(<CostsTabClient sku="SKU-1" />);

    // Abrir el sheet.
    await waitFor(() => screen.getByTestId("costs-add"));
    await userEvent.click(screen.getByTestId("costs-add"));

    // El input de fecha por defecto = hoy (2026-05-30).
    const dateInput = (await screen.findByTestId(
      "cost-valid-from",
    )) as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-06-15" } });

    await userEvent.click(screen.getByTestId("cost-submit"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledTimes(1);
    });
    const payload = createSpy.mock.calls[0]![0];
    expect(payload).toEqual(
      expect.objectContaining({ sku: "SKU-1", valid_from: "2026-06-15" }),
    );
    // No debe construir un datetime ISO ni usar effective_at.
    expect(payload.valid_from).toBe("2026-06-15");
    expect(payload.effective_at).toBeUndefined();
  });
});

describe("CostTable — badge de estado por rango de fechas", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-30T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renderiza Vigente / Programado / Caducado según valid_from/valid_to", () => {
    const costs: Cost[] = [
      makeCost({ id: "vig", valid_from: "2026-01-01", valid_to: null }),
      makeCost({ id: "prog", valid_from: "2026-09-01", valid_to: null }),
      makeCost({
        id: "cad",
        valid_from: "2025-01-01",
        valid_to: "2025-12-31",
      }),
    ];
    renderWithProviders(
      <CostTable costs={costs} showHistory canWrite={false} />,
    );

    expect(
      within(screen.getByTestId("cost-row-vig")).getByText("Vigente"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("cost-row-prog")).getByText("Programado"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("cost-row-cad")).getByText("Caducado"),
    ).toBeInTheDocument();
  });
});
