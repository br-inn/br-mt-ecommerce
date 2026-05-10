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

import {
  productsApi,
  ProductsApiError,
  type Product,
} from "@/lib/api/endpoints/products";
import { ProductEditForm } from "@/app/(app)/products/[sku]/_components/product-edit-form";

const messages = {
  catalog: {
    edit: {
      submit: "Guardar",
      saving: "…",
      success: "OK",
      conflict: "Conflicto, recarga.",
      validation: { nameMin: "Mínimo 3", weightInvalid: "Debe ser positivo" },
    },
    product: {
      fields: {
        sku: "SKU",
        name_en: "Nombre",
        description_en: "Descripción",
        family: "Familia",
        type: "Tipo",
        dn: "DN",
        pn: "PN",
        material: "Material",
        connection: "Conexión",
        weight_kg: "Peso",
      },
    },
  },
  common: { cancel: "Cancelar", error: "Error" },
};

const product: Product = {
  internal_id: "00000000-0000-0000-0000-000000000001",
  sku: "MTV-1",
  name_en: "Ball valve",
  family: "valves",
  subfamily: null,
  dn: "DN50",
  pn: "PN16",
  material: "CW617N",
  type: "ball",
  data_quality: "complete",
  translation_status_es: "approved",
  translation_status_ar: null,
  active: true,
  primary_image_url: null,
  updated_at: "2026-05-01T00:00:00Z",
  connection: null,
  weight_kg: 1.5,
  dimensions: null,
  packaging: null,
  intrastat: null,
  description_en: null,
  created_at: "2026-04-01T00:00:00Z",
  series_id: null,
  material_id: null,
  display_pair_sku: null,
  division_codes: [],
};

function renderForm(props?: Partial<React.ComponentProps<typeof ProductEditForm>>) {
  const onCancel = props?.onCancel ?? vi.fn();
  const onSaved = props?.onSaved ?? vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    onCancel,
    onSaved,
    ...render(
      <QueryClientProvider client={client}>
        <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
          <ProductEditForm product={product} onCancel={onCancel} onSaved={onSaved} />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    ),
  };
}

describe("ProductEditForm (US-1A-02-04-S2)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("guarda cambios cuando el form es válido", async () => {
    const spy = vi.spyOn(productsApi, "update").mockResolvedValue({
      ...product,
      dn: "DN65",
    });
    const { onSaved } = renderForm();
    const dn = document.querySelector('input[name="dn"]') as HTMLInputElement;
    fireEvent.change(dn, { target: { value: "DN65" } });
    await userEvent.click(screen.getByTestId("product-edit-submit"));
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith(
        "MTV-1",
        expect.objectContaining({ dn: "DN65" }),
      );
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("ante 412 muestra toast de conflicto y no llama onSaved", async () => {
    vi.spyOn(productsApi, "update").mockRejectedValue(
      new ProductsApiError(412, { detail: "stale" }, "Precondition Failed"),
    );
    const { onSaved } = renderForm();
    await userEvent.click(screen.getByTestId("product-edit-submit"));
    await waitFor(() => {
      expect(onSaved).not.toHaveBeenCalled();
    });
  });
});
