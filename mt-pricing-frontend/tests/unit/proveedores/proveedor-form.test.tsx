import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { suppliersApi, SuppliersApiError } from "@/lib/api/endpoints/suppliers";
import { ProveedorFormClient } from "@/app/(app)/proveedores/_components/proveedor-form-client";

const messages = {
  suppliers: {
    form: {
      submitCreate: "Crear",
      submitEdit: "Guardar",
      created: "Creado.",
      updated: "Actualizado.",
      errors: { duplicateCode: "Ya existe ese código." },
      validation: {
        codeRequired: "Código obligatorio.",
        codeFormat: "Formato inválido.",
        nameMin: "Mínimo 2 caracteres.",
        emailInvalid: "Email inválido.",
        leadTimeInvalid: "Debe ser >= 0.",
        currencyRequired: "Moneda obligatoria.",
      },
    },
  },
  proveedores: {
    fields: {
      code: "Código",
      name: "Nombre",
      contract_currency: "Moneda",
      lead_time_days: "Lead time",
      contact_email: "Email",
      contact_phone: "Teléfono",
      payment_terms_days: "Términos de pago",
      notes: "Notas",
      active: "Activo",
    },
  },
  common: { cancel: "Cancelar", loading: "…", error: "Error" },
};

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <ProveedorFormClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("ProveedorFormClient (US-1A-03-02 frontend)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("crea un proveedor cuando el form es válido", async () => {
    const created = vi.spyOn(suppliersApi, "create").mockResolvedValue({
      code: "ACME_001",
      name: "ACME",
      contract_currency: "AED",
      lead_time_days: 30,
      contact_email: null,
      contact_phone: null,
      payment_terms: null,
      notes: null,
      active: true,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
    });
    renderForm();
    const code = document.querySelector(
      'input[name="code"]',
    ) as HTMLInputElement;
    const name = document.querySelector(
      'input[name="name"]',
    ) as HTMLInputElement;
    fireEvent.change(code, { target: { value: "ACME_001" } });
    fireEvent.change(name, { target: { value: "ACME" } });

    await userEvent.click(screen.getByTestId("proveedor-submit"));
    await waitFor(() => {
      expect(created).toHaveBeenCalledWith(
        expect.objectContaining({ code: "ACME_001", name: "ACME" }),
      );
    });
  });

  it("propaga error 409 a field error en code", async () => {
    vi.spyOn(suppliersApi, "create").mockRejectedValue(
      new SuppliersApiError(409, { detail: "duplicate" }, "Conflict"),
    );
    renderForm();
    const code = document.querySelector(
      'input[name="code"]',
    ) as HTMLInputElement;
    const name = document.querySelector(
      'input[name="name"]',
    ) as HTMLInputElement;
    fireEvent.change(code, { target: { value: "DUP" } });
    fireEvent.change(name, { target: { value: "Dup Co" } });
    await userEvent.click(screen.getByTestId("proveedor-submit"));
    await waitFor(() => {
      expect(screen.getByText("Ya existe ese código.")).toBeInTheDocument();
    });
  });
});
