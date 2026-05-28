/**
 * 23 — `/pricing-desk` Pricing Desk — selectores y recarga de catálogo @critico.
 *
 * Cubre:
 *  - Pantalla carga y muestra "PRICING DESK" en el header
 *  - Selectores de Canal y Modelo visibles con valores por defecto
 *  - Cambio de canal → catálogo recarga (GET /catalog con nuevo canal)
 *  - Semáforo de KPIs renderiza tras carga del catálogo
 *  - Botón "Optimización completa" visible y pide confirmación en 1er click
 */

import { expect, test } from "@playwright/test";
import type { Route } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";

// ─── Seed data ──────────────────────────────────────────────────────────────

const FIXED_NOW = "2026-05-28T10:00:00Z";

const FAKE_CATALOG_SUMMARY = {
  semaforo: {
    total: 120,
    publishable: 95,
    blocked: 8,
    in_loss: 5,
    by_scheme: {
      canal_full: 60,
      canal_lastmile: 35,
      merchant_managed: 25,
    },
  },
  rows: [
    {
      sku: "MTV-1004",
      name_en: "Valve DN50 PN16",
      family_id: "fam-valves",
      family_name: "Valves",
      signal: "ÓPTIMO",
      margin_pct: 0.25,
      price_aed: "189.50",
      scheme_code: "canal_full",
      has_override: false,
    },
    {
      sku: "MTV-1005",
      name_en: "Valve DN80 PN16",
      family_id: "fam-valves",
      family_name: "Valves",
      signal: "FRÁGIL",
      margin_pct: 0.12,
      price_aed: "320.00",
      scheme_code: "canal_lastmile",
      has_override: false,
    },
  ],
};

const FAKE_PARAMS = {
  route: {
    id: "route-1",
    channel_id: "channel-amazon-uae",
    fx_rate: "4.0500",
    freight_cost_pct: "0.05",
    customs_duty_pct: "0.05",
    vat_pct: "0.05",
    updated_at: FIXED_NOW,
  },
  fees: {
    id: "fee-1",
    channel_id: "channel-amazon-uae",
    referral_fee_pct: "0.08",
    fba_fee_aed: "5.00",
    storage_fee_monthly_aed: "1.50",
    ads_pct: "0.03",
    updated_at: FIXED_NOW,
    total_fees_pct: 0.11,
  },
  schemes: [
    {
      id: "scheme-1",
      channel_id: "channel-amazon-uae",
      fulfillment_scheme: "canal_full",
      scheme_label: "FBA",
      is_available: true,
      flat_supplement_aed: 0,
      pct_surcharge: 0,
      max_weight_kg: null,
    },
    {
      id: "scheme-2",
      channel_id: "channel-amazon-uae",
      fulfillment_scheme: "canal_lastmile",
      scheme_label: "Last Mile",
      is_available: true,
      flat_supplement_aed: 2,
      pct_surcharge: 0.02,
      max_weight_kg: 30,
    },
    {
      id: "scheme-3",
      channel_id: "channel-amazon-uae",
      fulfillment_scheme: "merchant_managed",
      scheme_label: "Merchant",
      is_available: true,
      flat_supplement_aed: 0,
      pct_surcharge: 0,
      max_weight_kg: null,
    },
  ],
};

const FAKE_MARGIN_TARGETS = [
  {
    id: "mt-1",
    channel_id: "channel-amazon-uae",
    family_id: "fam-valves",
    family_name: "Valves",
    selling_model: "b2c",
    target_margin_pct: "0.25",
    updated_at: FIXED_NOW,
  },
  {
    id: "mt-2",
    channel_id: "channel-amazon-uae",
    family_id: "fam-fittings",
    family_name: "Fittings",
    selling_model: "b2c",
    target_margin_pct: "0.20",
    updated_at: FIXED_NOW,
  },
];

const FAKE_OPTIMIZE_RESPONSE = {
  channel_id: "channel-amazon-uae",
  selling_model: "b2c",
  applied: 95,
  skipped: 5,
  errors: 0,
};

// ─── Install mocks ───────────────────────────────────────────────────────────

function installPricingDeskMocks(page: { route: (url: string | RegExp, handler: (route: Route) => Promise<void>) => void }): void {
  // Catalog summary — Amazon UAE
  page.route(/\/api\/v1\/pricing\/amazon_uae\/catalog(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_CATALOG_SUMMARY),
    });
  });

  // Catalog summary — Noon UAE (different channel to assert reload)
  page.route(/\/api\/v1\/pricing\/noon_uae\/catalog(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...FAKE_CATALOG_SUMMARY,
        semaforo: { ...FAKE_CATALOG_SUMMARY.semaforo, total: 85 },
      }),
    });
  });

  // Pricing params (cost side panel)
  page.route(/\/api\/v1\/pricing\/[^/]+\/params(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_PARAMS),
    });
  });

  // Margin targets
  page.route(/\/api\/v1\/pricing\/[^/]+\/margin-targets(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_MARGIN_TARGETS),
    });
  });

  // Optimize apply
  page.route(/\/api\/v1\/pricing\/[^/]+\/optimize\/apply(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_OPTIMIZE_RESPONSE),
    });
  });

  // Optimize preview
  page.route(/\/api\/v1\/pricing\/[^/]+\/optimize(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_OPTIMIZE_RESPONSE),
    });
  });

  // Route params patch
  page.route(/\/api\/v1\/pricing\/[^/]+\/route-params$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_PARAMS.route),
    });
  });

  // Fee params patch
  page.route(/\/api\/v1\/pricing\/[^/]+\/fee-params$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_PARAMS.fees),
    });
  });

  // Margin targets upsert
  page.route(/\/api\/v1\/pricing\/[^/]+\/margin-targets$/, async (route: Route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fallback();
  });

  // Margin overrides
  page.route(/\/api\/v1\/pricing\/[^/]+\/margin-overrides\/[^/]+(\?.*)?$/, async (route: Route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "ov-1",
        channel_id: "channel-amazon-uae",
        sku: "MTV-1004",
        selling_model: "b2c",
        margin_pct: "0.30",
        created_at: FIXED_NOW,
      }),
    });
  });
}

// ─── Tests ───────────────────────────────────────────────────────────────────

test.describe("Pricing Desk — selectores y recarga de catálogo @critico", () => {
  test.beforeEach(async ({ page }) => {
    installPricingDeskMocks(page);
    await loginAsGerente(page);
  });

  test("carga y muestra el título PRICING DESK", async ({ page }) => {
    await page.goto("/pricing-desk");
    await expect(page.getByText("PRICING DESK")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("selector de canal visible con Amazon UAE por defecto", async ({ page }) => {
    await page.goto("/pricing-desk");
    const canalSelect = page.locator("select").filter({ hasText: /Amazon UAE/i }).first();
    await expect(canalSelect).toBeVisible({ timeout: 15_000 });
    await expect(canalSelect).toHaveValue("amazon_uae");
  });

  test("selector de modelo de venta visible con B2C por defecto", async ({ page }) => {
    await page.goto("/pricing-desk");
    // Esperar a que la página cargue primero
    await expect(page.getByText("PRICING DESK")).toBeVisible({ timeout: 15_000 });
    const modeloSelect = page.locator("select").filter({ hasText: /B2C/i }).first();
    await expect(modeloSelect).toBeVisible({ timeout: 5_000 });
    await expect(modeloSelect).toHaveValue("b2c");
  });

  test("cambiar canal a Noon UAE recarga el catálogo", async ({ page }) => {
    await page.goto("/pricing-desk");
    await expect(page.getByText("PRICING DESK")).toBeVisible({ timeout: 15_000 });

    // Interceptar la llamada al catálogo de Noon UAE
    const catalogRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/pricing/noon_uae/catalog") &&
        req.method() === "GET",
      { timeout: 10_000 },
    );

    // Cambiar canal al selector
    const canalSelect = page.locator("select").filter({ hasText: /Amazon UAE/i }).first();
    await canalSelect.selectOption("noon_uae");

    // Verificar que se disparó la petición al nuevo canal
    await catalogRequest;
  });

  test("semáforo de KPI cards renderiza tras carga del catálogo", async ({ page }) => {
    await page.goto("/pricing-desk");
    // Esperar a que los datos del catálogo carguen (KpiCard muestra datos del seed)
    await expect(page.getByText("Catálogo")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Publicables")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Bloqueados")).toBeVisible({ timeout: 5_000 });
  });

  test("botón Optimización completa pide confirmación en 1er click", async ({ page }) => {
    await page.goto("/pricing-desk");
    await expect(page.getByText("PRICING DESK")).toBeVisible({ timeout: 15_000 });

    const optimizeBtn = page.getByRole("button", {
      name: /Optimización completa/i,
    });
    await expect(optimizeBtn).toBeVisible({ timeout: 10_000 });

    // Primer click → debe cambiar a estado de confirmación
    await optimizeBtn.click();
    await expect(
      page.getByRole("button", { name: /Confirmas/i }),
    ).toBeVisible({ timeout: 3_000 });
  });
});
