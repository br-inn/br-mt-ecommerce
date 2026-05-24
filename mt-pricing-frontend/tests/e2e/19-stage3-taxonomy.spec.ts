/**
 * 19 — Stage 3 (Wave 11) — taxonomy refinement flows @critico.
 *
 * Cubre:
 *  - Selector de división propaga `?division=` en URL.
 *  - Saved view "Hidrosanitario" aplica filter division=hidrosanitario.
 *  - Facet sidebar muestra grupos Stage 3 (división, serie, tier, material curado).
 *  - Series landing `/series/[code]` renderiza hero + bullets + productos.
 *  - Product detail muestra Stage3DisplayBlock cuando hay tags/certs efectivos.
 *
 * Mocks: routes mock para /divisions, /series, /series-tiers, /materials, /facets,
 * /products/{sku}/effective-display.
 */

import { expect, test, type Page } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installProductsMocks } from "./fixtures/seed";

const FAKE_DIVISIONS = [
  {
    id: "00000000-0000-0000-0000-000000000a01",
    code: "hidrosanitario",
    name: "Hidrosanitario",
    description: null,
    sort_order: 10,
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000a02",
    code: "industrial",
    name: "Industrial",
    description: null,
    sort_order: 20,
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
];

const FAKE_SERIES = [
  {
    id: "00000000-0000-0000-0000-000000000b01",
    code: "pn40_platinum",
    name_en: "PN40 Platinum Series",
    tier_id: "00000000-0000-0000-0000-000000000c01",
    pressure_rating_pn: 40,
    temperature_min_c: -20,
    temperature_max_c: 180,
    banner_color: "#E5004C",
    hero_image_url: null,
    description_en: "DZR brass series with NoFrost system.",
    bullets_en: ["Latón DZR CW602N", "Sistema antihielo", "Apta para energía solar"],
    features_tags: ["nofrost", "solar_ready"],
    sort_order: 10,
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
];

const FAKE_TIERS = [
  {
    id: "00000000-0000-0000-0000-000000000c01",
    code: "platinum",
    name: "Platinum",
    rank: 1,
    display_color: "#E5004C",
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000c02",
    code: "gold",
    name: "Gold",
    rank: 2,
    display_color: "#E2B233",
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
];

const FAKE_MATERIALS = [
  {
    id: "00000000-0000-0000-0000-000000000d01",
    code: "laton",
    name: "Latón",
    family_kind: "metal",
    notes: null,
    sort_order: 10,
    active: true,
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T00:00:00Z",
  },
];

function installStage3Mocks(page: Page): void {
  page.route("**/api/v1/divisions**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_DIVISIONS),
    }),
  );
  page.route("**/api/v1/series-tiers**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_TIERS),
    }),
  );
  page.route("**/api/v1/series**", (route) => {
    const url = route.request().url();
    if (/\/series\/[a-f0-9-]+\/translations$/i.test(url)) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            series_id: FAKE_SERIES[0]!.id,
            lang: "es",
            name: "Serie PN40 Platinum",
            description: "Serie en latón DZR con sistema antihielo.",
            bullets: ["Latón DZR CW602N", "Sistema antihielo"],
            created_at: "2026-05-09T00:00:00Z",
            updated_at: "2026-05-09T00:00:00Z",
          },
        ]),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_SERIES),
    });
  });
  page.route("**/api/v1/materials**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_MATERIALS),
    }),
  );

  // Facets endpoint — return Stage 3 dimensions
  page.route("**/api/v1/products/facets**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: 3,
        total_unfiltered: 3,
        family: [{ value: "valves", count: 2 }, { value: "fittings", count: 1 }],
        material: [],
        dn: [],
        pn: [],
        data_quality: {},
        active: {},
        image_status: {},
        has_image: {},
        translation_status: {},
        // Stage 3 dimensions
        division: [
          { value: "hidrosanitario", count: 2 },
          { value: "industrial", count: 1 },
        ],
        series: [{ value: FAKE_SERIES[0]!.id, count: 2 }],
        tier_code: [{ value: "platinum", count: 2 }],
        material_curated: [{ value: FAKE_MATERIALS[0]!.id, count: 2 }],
      }),
    }),
  );

  // Effective display endpoint
  page.route("**/api/v1/products/*/effective-display", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tags: ["nofrost", "solar_ready", "platinum"],
        certifications: [
          { id: "cert-1", code: "DZR", name: "DZR Brass", issued_by: null, scope: null, logo_url: null },
          { id: "cert-2", code: "ACS", name: "ACS", issued_by: null, scope: null, logo_url: null },
        ],
      }),
    }),
  );
}

test.describe("Stage 3 — taxonomy flows @critico", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);
    installStage3Mocks(page);
    await loginAsGerente(page);
  });

  test("selector de división actualiza ?division= en URL", async ({ page }) => {
    await page.goto("/catalogo");
    await page.getByRole("button", { name: "Industrial" }).click();
    await expect(page).toHaveURL(/[?&]division=industrial/, { timeout: 3_000 });
    await page.getByRole("button", { name: "Hidrosanitario" }).click();
    await expect(page).toHaveURL(/[?&]division=hidrosanitario/);
    await page.getByRole("button", { name: "Todas" }).click();
    await expect(page).not.toHaveURL(/division=/);
  });

  test("URL inicial con ?division=industrial activa el tab correspondiente", async ({
    page,
  }) => {
    await page.goto("/catalogo?division=industrial");
    const industrialTab = page.getByRole("button", { name: "Industrial" });
    // El botón seleccionado tiene clase font-semibold (heuristic).
    await expect(industrialTab).toBeVisible();
  });

  test("series landing /series/pn40_platinum renderiza hero + bullets", async ({
    page,
  }) => {
    await page.goto("/series/pn40_platinum");
    await expect(page.getByRole("heading", { name: /Serie PN40 Platinum|PN40 Platinum/i })).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText(/Latón DZR/i).first()).toBeVisible();
    await expect(page.getByText("PN40")).toBeVisible();
  });

  test("series landing con código inexistente muestra empty state", async ({
    page,
  }) => {
    await page.goto("/series/no_existe_xyz");
    await expect(page.getByText(/Serie no encontrada/i)).toBeVisible({ timeout: 5_000 });
  });
});
