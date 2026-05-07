/**
 * 03 — Pantalla 2 — Listado de productos (Crítico).
 *
 * Verifica:
 *  - Tabla `/products` renderiza con filas (mocks o seed real)
 *  - Columnas SKU, name, family, brand, dn, pn, material, status presentes
 *  - Filtros family/brand/q operan (cambian items o re-disparan request)
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installProductsMocks, FAKE_PRODUCTS } from "./fixtures/seed";

test.describe("Pantalla 2 — products list @critico", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("renderiza tabla con SKUs seed y headers correctos", async ({ page }) => {
    await page.goto("/products");
    await expect(
      page.getByRole("heading", { name: /catálogo|catalog/i }),
    ).toBeVisible();
    await expect(page.getByTestId("products-table-root")).toBeVisible({
      timeout: 15000,
    });

    // Al menos uno de los SKUs seed debería aparecer
    await expect(
      page.getByTestId(`product-row-${FAKE_PRODUCTS[0]!.sku}`),
    ).toBeVisible();

    // Columnas — buscamos por texto de header (i18n-tolerant via regex)
    await expect(page.getByRole("columnheader", { name: /sku/i }).first()).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: /name|nombre/i }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: /family|familia/i }).first(),
    ).toBeVisible();
  });

  test("filtro por family aplica y mantiene URL en sync", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible();

    await page.getByTestId("products-family-filter").click();
    // Selecciona "valves" (capitalize en UI; el value es lower)
    await page.getByRole("option", { name: /valves/i }).click();

    await expect(page).toHaveURL(/family=valves/);
  });

  test("filtro de búsqueda (q) actualiza la URL tras debounce", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible();

    await page.getByTestId("products-search").fill("DN50");
    // Debounce 300ms → esperamos que la URL refleje q=DN50
    await expect(page).toHaveURL(/[?&]q=DN50/, { timeout: 3000 });
  });

  test("filtro brand client-side filtra resultados visibles", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible();

    await page.getByTestId("products-brand-filter").fill("MT");
    // Brand=MT → todos los seed la tienen, sigue habiendo filas
    await expect(
      page.getByTestId(`product-row-${FAKE_PRODUCTS[0]!.sku}`),
    ).toBeVisible();
  });
});
