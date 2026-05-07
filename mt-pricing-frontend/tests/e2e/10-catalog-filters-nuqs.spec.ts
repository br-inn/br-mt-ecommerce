/**
 * 10 — Catálogo `/catalogo` filtros nuqs (q / family / quality / dn / pn / material) @critico.
 *
 * `/catalogo/page.tsx` (S3) usa `useQueryState` de nuqs para mantener filtros
 * sincronizados con la URL. Aquí verificamos:
 *  - search debounced actualiza `?q=`
 *  - panel "Más filtros" con DN/PN/material refleja en URL
 *  - chip de family con botón quitar limpia el query param
 *
 * Selectores: la página NO usa `data-testid`. Usamos `getByPlaceholder` para el
 * search input y `getByLabel` (label visible "DN", "PN", "material") para los
 * selects.
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installProductsMocks } from "./fixtures/seed";

test.describe("Catálogo — filtros nuqs @critico", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);
    await loginAsGerente(page);
  });

  test("search input con debounce actualiza ?q=", async ({ page }) => {
    await page.goto("/catalogo");
    // El header del page muestra "SKUs"
    await expect(page.getByRole("heading").first()).toBeVisible();

    const search = page.getByPlaceholder(/Buscar SKU/i);
    await search.fill("VAL-DN50");
    await expect(page).toHaveURL(/[?&]q=VAL-DN50/, { timeout: 3_000 });
  });

  test("more-filters panel: DN50 + PN16 + brass → URL contiene los 3", async ({
    page,
  }) => {
    await page.goto("/catalogo");

    // Abrir panel "Filtros · N"
    await page
      .getByRole("button", { name: /^Filtros\s*·/i })
      .click();

    // Selects identificados por su label visible
    await page.getByLabel("DN").selectOption("DN50");
    await page.getByLabel("PN").selectOption("PN16");
    await page.getByLabel("material").selectOption("brass");

    await expect(page).toHaveURL(/dn=DN50/);
    await expect(page).toHaveURL(/pn=PN16/);
    await expect(page).toHaveURL(/material=brass/);
  });

  test("URL inicial con family=valves → chip activo + botón quitar", async ({
    page,
  }) => {
    await page.goto("/catalogo?family=valves");
    // Chip "family: valves" visible
    await expect(page.getByText(/family:\s*valves/i)).toBeVisible({
      timeout: 10_000,
    });
    // Botón aria-label "Quitar filtro family"
    await page.getByRole("button", { name: /Quitar filtro family/i }).click();
    await expect(page).not.toHaveURL(/family=valves/);
  });

  test("Limpiar todo elimina múltiples params de la URL", async ({ page }) => {
    await page.goto("/catalogo?dn=DN50&pn=PN16&material=brass");
    await expect(page.getByText(/DN:\s*DN50/i)).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("button", { name: /Limpiar todo/i }).click();
    await expect(page).not.toHaveURL(/dn=DN50/);
    await expect(page).not.toHaveURL(/material=brass/);
  });
});
