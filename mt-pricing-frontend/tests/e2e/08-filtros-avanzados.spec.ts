/**
 * 08 — Filtros avanzados Pantalla 2 (Secundario).
 *
 * Cubre el Sheet "Más filtros" del listado de productos:
 *  - Abre el Sheet → DN20, material=brass → aplica → chips activos
 *  - Limpiar filtros restablece la URL
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installProductsMocks } from "./fixtures/seed";

test.describe("Pantalla 2 — filtros avanzados @secundario", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("Sheet más filtros: DN20 + material=brass → chips visibles", async ({
    page,
  }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible({
      timeout: 15000,
    });

    await page.getByTestId("products-more-filters").click();

    await page.getByTestId("products-dn-filter").fill("DN20");
    await page.getByTestId("products-material-filter").fill("brass");

    // Cerrar Sheet con "Aplicar"
    await page.getByRole("button", { name: /aplicar|apply/i }).click();

    // URL debe contener dn=DN20 y material=brass
    await expect(page).toHaveURL(/dn=DN20/);
    await expect(page).toHaveURL(/material=brass/);

    // Chips activos visibles
    await expect(page.getByTestId("products-filter-chips")).toBeVisible();
  });

  test("clear filtros vacía la URL", async ({ page }) => {
    await page.goto("/products?dn=DN20&material=brass");
    await expect(page.getByTestId("products-table-root")).toBeVisible();
    await expect(page.getByTestId("products-clear-filters")).toBeVisible();
    await page.getByTestId("products-clear-filters").click();
    await expect(page).not.toHaveURL(/dn=DN20/);
    await expect(page).not.toHaveURL(/material=brass/);
  });
});
