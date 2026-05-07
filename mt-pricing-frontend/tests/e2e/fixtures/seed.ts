/**
 * Mocks de payloads del backend para tests "puros UI" (sin DB real).
 *
 * Mantienen contrato del API en sync con `lib/api/endpoints/*`. Cuando el
 * orquestador corre con DB real, los tests pueden saltarse los mocks (toggle
 * via `installCatalogMocks` opcional).
 */

import type { Page } from "@playwright/test";

export interface FakeProduct {
  id: string;
  sku: string;
  name_en: string;
  family: string;
  brand?: string | null;
}

export const FAKE_PRODUCTS: FakeProduct[] = [
  {
    id: "p-001",
    sku: "VAL-DN50-PN16",
    name_en: "Valve DN50 PN16",
    family: "valves",
    brand: "MT",
  },
  {
    id: "p-002",
    sku: "FIT-ELB-90",
    name_en: "Elbow 90",
    family: "fittings",
    brand: "MT",
  },
  {
    id: "p-003",
    sku: "VAL-DN20-BR",
    name_en: "Brass valve DN20",
    family: "valves",
    brand: "MT",
  },
];

export function commonProductFields(p: FakeProduct): Record<string, unknown> {
  return {
    ...p,
    dn: p.sku.includes("DN20") ? "DN20" : "DN50",
    pn: "PN16",
    material: p.sku.includes("BR") ? "brass" : "steel",
    type: null,
    connection: null,
    weight_kg: 1.5,
    dimensions: null,
    packaging: null,
    intrastat: null,
    description_en: null,
    data_quality: "complete",
    translation_status_es: "approved",
    translation_status_ar: "draft",
    active: true,
    primary_image_url: null,
    created_at: "2026-05-06T12:00:00Z",
    updated_at: "2026-05-06T12:00:00Z",
  };
}

export function installProductsMocks(page: Page): void {
  page.route("**/api/v1/products?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: FAKE_PRODUCTS.map(commonProductFields),
        next_cursor: null,
        total: FAKE_PRODUCTS.length,
      }),
    });
  });

  page.route("**/api/v1/products/*", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const skuOrId = url.split("/").pop()?.split("?")[0] ?? "";
    const found =
      FAKE_PRODUCTS.find((p) => p.sku === skuOrId || p.id === skuOrId) ??
      FAKE_PRODUCTS[0]!;
    if (method === "PATCH") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...commonProductFields(found), ...body }),
      });
      return;
    }
    if (method === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(commonProductFields(found)),
    });
  });

  page.route("**/api/v1/products/*/images", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

export function installSuppliersMocks(page: Page): void {
  // Lista vacía por defecto — el test de CRUD añade vía route override.
  let store: Array<Record<string, unknown>> = [];

  page.route("**/api/v1/suppliers?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: store, next_cursor: null, total: store.length }),
    });
  });

  page.route("**/api/v1/suppliers", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const created = {
        id: `sup-${Date.now()}`,
        ...body,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      store.push(created);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(created),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: store, next_cursor: null, total: store.length }),
    });
  });

  page.route("**/api/v1/suppliers/*", async (route) => {
    const method = route.request().method();
    const id = route.request().url().split("/").pop()?.split("?")[0] ?? "";
    const found = store.find((s) => s["id"] === id);
    if (method === "PATCH") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      const updated = { ...found, ...body };
      store = store.map((s) => (s["id"] === id ? updated : s));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(updated),
      });
      return;
    }
    if (method === "DELETE") {
      store = store.filter((s) => s["id"] !== id);
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(found ?? {}),
    });
  });
}

export function installImportsMocks(page: Page): void {
  page.route("**/api/v1/imports/preview", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ status: 405, body: "" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "import-preview-001",
        rows_total: 5085,
        rows_new: 4500,
        rows_updated: 500,
        rows_unchanged: 80,
        rows_invalid: 5,
        diff: [
          {
            row: 1,
            sku: "VAL-DN50-PN16",
            action: "update",
            changes: { name_en: { from: "old", to: "new" } },
          },
        ],
        warnings: [],
        errors: [],
      }),
    });
  });
}
