/**
 * E2E del Catálogo (Sprint 1).
 *
 * Estrategia idéntica a `auth.spec.ts`: interceptamos Supabase + backend para
 * dar al frontend una sesión y datos de productos sintéticos.
 */

import { expect, test, type Page } from "@playwright/test";

const FAKE_USER_ID = "11111111-1111-1111-1111-111111111111";
const FAKE_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature";

interface FakeProduct {
  id: string;
  sku: string;
  name_en: string;
  family: string;
}

const FAKE_PRODUCTS: FakeProduct[] = [
  { id: "p-001", sku: "VAL-DN50-PN16", name_en: "Valve DN50 PN16", family: "valves" },
  { id: "p-002", sku: "FIT-ELB-90", name_en: "Elbow 90", family: "fittings" },
];

function commonProductFields(p: FakeProduct) {
  return {
    ...p,
    dn: "DN50",
    pn: "PN16",
    material: "steel",
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

function installAuthMocks(page: Page) {
  page.route("**/auth/v1/token**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: FAKE_ACCESS_TOKEN,
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: "fake-refresh",
        user: {
          id: FAKE_USER_ID,
          email: "e2e@mt.ae",
          app_metadata: {},
          user_metadata: { full_name: "E2E User" },
        },
      }),
    });
  });
  page.route("**/auth/v1/user**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: "e2e@mt.ae",
        user_metadata: { full_name: "E2E User" },
      }),
    });
  });
  page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: "e2e@mt.ae",
        full_name: "E2E User",
        avatar_url: null,
        locale: "es",
        is_active: true,
        role: { id: "r-1", code: "gerente", name: "Gerente" },
        last_login_at: null,
        created_at: "2026-05-06T12:00:00Z",
        permissions: [
          "products:read",
          "products:write",
          "products:delete",
          "translations:approve",
          "imports:execute",
        ],
      }),
    });
  });
}

function installCatalogMocks(page: Page) {
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
  page.route("**/api/v1/products", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { sku?: string; name_en?: string };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          ...commonProductFields({
            id: "new-id",
            sku: body.sku ?? "NEW-SKU",
            name_en: body.name_en ?? "New",
            family: "valves",
          }),
        }),
      });
      return;
    }
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
      FAKE_PRODUCTS.find((p) => p.sku === skuOrId || p.id === skuOrId) ?? FAKE_PRODUCTS[0]!;
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
  page.route("**/api/v1/products/*/translations", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          language: "es",
          name: "Válvula DN50",
          description: null,
          status: "approved",
          updated_at: "2026-05-06T12:00:00Z",
          approved_at: "2026-05-06T12:00:00Z",
          approved_by: FAKE_USER_ID,
        },
        {
          language: "ar",
          name: null,
          description: null,
          status: "draft",
          updated_at: "2026-05-06T12:00:00Z",
          approved_at: null,
          approved_by: null,
        },
      ]),
    });
  });
  page.route("**/api/v1/products/*/translations/**", async (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const lang = url.includes("/ar") ? "ar" : "es";
    if (method === "PUT") {
      const body = route.request().postDataJSON() as { name?: string; description?: string };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          language: lang,
          name: body.name ?? null,
          description: body.description ?? null,
          status: "draft",
          updated_at: "2026-05-06T12:00:00Z",
          approved_at: null,
          approved_by: null,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        language: lang,
        name: "Approved",
        description: null,
        status: "approved",
        updated_at: "2026-05-06T12:00:00Z",
        approved_at: "2026-05-06T12:00:00Z",
        approved_by: FAKE_USER_ID,
      }),
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

async function login(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: /usar contraseña|use password/i }).click();
  await page.getByLabel(/correo|email/i).fill("e2e@mt.ae");
  await page.getByLabel(/contraseña|password/i).fill("super-secret-pass");
  await page.getByRole("button", { name: /entrar|sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
}

test.describe("Catalog flow", () => {
  test("lists products and navigates to detail", async ({ page }) => {
    installAuthMocks(page);
    installCatalogMocks(page);
    await login(page);

    await page.goto("/catalogo");
    await expect(page.getByRole("heading", { name: /catálogo|catalog/i })).toBeVisible();
    await expect(page.getByText("VAL-DN50-PN16")).toBeVisible();
    await page.getByRole("link", { name: "VAL-DN50-PN16" }).click();
    await expect(page).toHaveURL(/\/catalogo\/VAL-DN50-PN16/);
    await expect(page.getByRole("heading", { name: /Valve DN50/i })).toBeVisible();
  });

  test("creates a new SKU through the wizard", async ({ page }) => {
    installAuthMocks(page);
    installCatalogMocks(page);
    await login(page);

    await page.goto("/catalogo/nuevo");
    await page.getByLabel(/^SKU$/).fill("NEW-SKU-001");
    await page.getByLabel(/Nombre.*EN|Name.*EN/i).fill("New widget");
    await page.getByRole("button", { name: /siguiente|next/i }).click();
    await page.getByRole("button", { name: /siguiente|next/i }).click();
    await page.getByRole("button", { name: /siguiente|next/i }).click();
    await page.getByRole("button", { name: /crear sku|create sku/i }).click();

    await expect(page).toHaveURL(/\/catalogo\/NEW-SKU/, { timeout: 10000 });
  });

  test("edits a translation in the translations tab", async ({ page }) => {
    installAuthMocks(page);
    installCatalogMocks(page);
    await login(page);

    await page.goto("/catalogo/VAL-DN50-PN16/traducciones");
    const arInput = page.getByLabel(/^name$/i).nth(1); // segundo card (AR)
    await arInput.fill("صمام");
    await page.getByRole("button", { name: /guardar borrador|save draft/i }).first().click();
    await expect(page.getByText(/borrador guardado|draft saved/i)).toBeVisible({
      timeout: 5000,
    });
  });
});
