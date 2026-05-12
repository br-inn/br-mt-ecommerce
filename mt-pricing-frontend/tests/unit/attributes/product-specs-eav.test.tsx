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

import { attributesApi } from "@/lib/api/endpoints/attributes";
import { ProductSpecsCardEAV } from "@/app/(app)/catalogo/[sku]/_components/product-specs-eav";
import type {
  AttributeValue,
  FamilyAttribute,
} from "@/lib/api/types-attributes";

const FAMILY_ID = "11111111-1111-1111-1111-111111111111";
const SKU = "MT-V-001";

function fa(overrides: Partial<FamilyAttribute>): FamilyAttribute {
  return {
    id: "fa-id",
    family_id: FAMILY_ID,
    attribute_id: "attr-id",
    group_code: "ball_general",
    order_index: 0,
    is_required: false,
    default_value: null,
    validation_rule: null,
    definition: {
      id: "attr-id",
      code: "dn",
      label_en: "DN",
      data_type: "number",
      unit: "mm",
      description_en: null,
      is_filterable: true,
      is_seo_relevant: false,
      scope: "product",
    },
    options: undefined,
    ...overrides,
  };
}

function val(overrides: Partial<AttributeValue>): AttributeValue {
  return {
    id: "v-id",
    owner_type: "product",
    owner_id: SKU,
    attribute_id: "attr-id",
    value_number: null,
    value_text: null,
    value_bool: null,
    value_enum_id: null,
    value_min: null,
    value_max: null,
    unit: null,
    language: null,
    ...overrides,
  };
}

function renderEAV(familyId: string | null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    React.createElement(
      QueryClientProvider,
      { client },
      React.createElement(ProductSpecsCardEAV, { sku: SKU, familyId }),
    ),
  );
}

describe("ProductSpecsCardEAV", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders an explanatory empty state when familyId is null", () => {
    renderEAV(null);
    expect(
      screen.getByText(/family uuid is not assigned/i),
    ).toBeInTheDocument();
  });

  it("renders one group card per group_code with humanised title", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([
      fa({
        id: "fa-1",
        attribute_id: "a1",
        group_code: "ball_general",
        definition: {
          id: "a1",
          code: "dn",
          label_en: "DN",
          data_type: "number",
          unit: "mm",
          description_en: null,
          is_filterable: true,
          is_seo_relevant: false,
          scope: "product",
        },
      }),
      fa({
        id: "fa-2",
        attribute_id: "a2",
        group_code: "ball_dimensions",
        definition: {
          id: "a2",
          code: "length",
          label_en: "Length",
          data_type: "number",
          unit: "mm",
          description_en: null,
          is_filterable: false,
          is_seo_relevant: false,
          scope: "product",
        },
      }),
    ]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      expect(screen.getByTestId("group-ball_general")).toBeInTheDocument();
      expect(screen.getByTestId("group-ball_dimensions")).toBeInTheDocument();
    });
    expect(screen.getByText("Ball general")).toBeInTheDocument();
    expect(screen.getByText("Ball dimensions")).toBeInTheDocument();
  });

  it("renders a number value with its unit", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([
      fa({ attribute_id: "a1" }),
    ]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([
      val({ attribute_id: "a1", value_number: 50 }),
    ]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      expect(screen.getByText("50 mm")).toBeInTheDocument();
    });
  });

  it("renders an enum value as the option's label_en", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([
      fa({
        attribute_id: "a1",
        definition: {
          id: "a1",
          code: "material",
          label_en: "Material",
          data_type: "enum",
          unit: null,
          description_en: null,
          is_filterable: true,
          is_seo_relevant: false,
          scope: "product",
        },
        options: [
          {
            id: "opt-1",
            attribute_id: "a1",
            code: "ss316",
            label_en: "Stainless Steel 316",
            order_index: 0,
          },
        ],
      }),
    ]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([
      val({ attribute_id: "a1", value_enum_id: "opt-1" }),
    ]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      expect(screen.getByText("Stainless Steel 316")).toBeInTheDocument();
    });
  });

  it("renders a range value as [min, max] + unit", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([
      fa({
        attribute_id: "a1",
        definition: {
          id: "a1",
          code: "temp_range",
          label_en: "Temp",
          data_type: "range",
          unit: "C",
          description_en: null,
          is_filterable: false,
          is_seo_relevant: false,
          scope: "product",
        },
      }),
    ]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([
      val({
        attribute_id: "a1",
        value_min: -10,
        value_max: 80,
      }),
    ]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      expect(screen.getByText("[-10, 80] C")).toBeInTheDocument();
    });
  });

  it("flags a required attribute with a destructive badge when no value is set", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([
      fa({ attribute_id: "a1", is_required: true }),
    ]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      const badges = screen.getAllByText(/required/i);
      expect(badges.length).toBeGreaterThan(0);
      const destructive = badges.find((b) =>
        b.className.includes("bg-destructive"),
      );
      expect(destructive).toBeTruthy();
    });
  });

  it("shows an empty-state card when the family has no template attributes", async () => {
    vi.spyOn(attributesApi, "listFamilyAttributes").mockResolvedValue([]);
    vi.spyOn(attributesApi, "listProductAttributeValues").mockResolvedValue([]);

    renderEAV(FAMILY_ID);

    await waitFor(() => {
      expect(
        screen.getByText(/no attribute template configured/i),
      ).toBeInTheDocument();
    });
  });
});
