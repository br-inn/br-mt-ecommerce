/**
 * 14 — `/precios/aprobaciones` filter chips + bulk-approve + per-row actions @critico.
 *
 * Cubre:
 *  - Tabla con propuestas pending del mock (2 rows)
 *  - Toggle FilterChip "Aprobadas" cambia el query (status=approved → mock 0 rows)
 *  - Click en checkbox header selecciona todas; aparece bulk action bar
 *  - Click bulk "Aprobar" dispara request (mock)
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installPricingMocks, FAKE_PRICES } from "./fixtures/seed-extended";

test.describe("Pricing approvals — bulk + per-row @critico", () => {
  test.beforeEach(async ({ page }) => {
    installPricingMocks(page);
    await loginAsGerente(page);
  });

  test("tabla muestra los SKUs pending del seed", async ({ page }) => {
    await page.goto("/precios/aprobaciones");
    await expect(
      page.getByText(/Bandeja del Gerente/i),
    ).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText(FAKE_PRICES[0]!.product_sku).first()).toBeVisible();
    await expect(page.getByText(FAKE_PRICES[1]!.product_sku).first()).toBeVisible();
  });

  test("FilterChip 'Aprobadas' cambia status filter → tabla vacía", async ({
    page,
  }) => {
    await page.goto("/precios/aprobaciones");
    await expect(
      page.getByText(FAKE_PRICES[0]!.product_sku).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Aprobadas$/i }).click();

    // El mock de pricing filtra por ?status=approved → []. Empty state aparece.
    await expect(page.getByText(/Sin resultados/i).first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("seleccionar todas + bulk approve dispara la action bar", async ({
    page,
  }) => {
    await page.goto("/precios/aprobaciones");
    await expect(
      page.getByText(FAKE_PRICES[0]!.product_sku).first(),
    ).toBeVisible({ timeout: 15_000 });

    // El checkbox del header es el primer checkbox visible en la tabla.
    const headerCheckbox = page.locator("thead input[type='checkbox']").first();
    await headerCheckbox.check();

    // Action bar muestra "N seleccionados"
    await expect(page.getByText(/seleccionado/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /^Aprobar$/i })).toBeVisible();

    // Click bulk approve — el mock devuelve approved=N
    await page.getByRole("button", { name: /^Aprobar$/i }).click();
    // Tras la mutación la action bar desaparece (selección reset).
    await expect(page.getByText(/seleccionado/i)).toHaveCount(0, {
      timeout: 5_000,
    });
  });

  test("per-row approve clickable via aria-label", async ({ page }) => {
    await page.goto("/precios/aprobaciones");
    await expect(
      page.getByText(FAKE_PRICES[0]!.product_sku).first(),
    ).toBeVisible({ timeout: 15_000 });

    const sku = FAKE_PRICES[0]!.product_sku;
    const approveBtn = page.getByRole("button", {
      name: new RegExp(`Aprobar ${sku}`, "i"),
    });
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    // El mock responde 200 → no error toast. Verificamos que el botón vuelve
    // a estar habilitado (no isPending stuck).
    await expect(approveBtn).toBeEnabled({ timeout: 5_000 });
  });
});
