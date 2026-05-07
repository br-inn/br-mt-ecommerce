/**
 * 05 — Suppliers CRUD (Crítico).
 *
 * Flow happy-path:
 *  1. `/suppliers` carga (lista vacía o con data)
 *  2. Click "Nuevo" → form `/suppliers/new`
 *  3. Rellenar code, name, country, currency=EUR, lead_time=7
 *  4. Submit → redirect al detalle + toast OK
 *  5. Volver al listado y verificar que aparece en la tabla
 *  6. Soft-deactivate via menú de acciones
 *
 * Cleanup: el `installSuppliersMocks` mantiene el store en memoria; en modo
 * real (DB), el orquestador limpia con `seed_demo.py --reset-suppliers`.
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installSuppliersMocks } from "./fixtures/seed";

const TEST_SUPPLIER_CODE = `E2E_TEST_${Date.now()}`;
const TEST_SUPPLIER_NAME = "Proveedor E2E Test";

test.describe("Suppliers CRUD @critico", () => {
  test.beforeEach(async ({ page }) => {
    installSuppliersMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("listado vacío muestra estado empty + CTA nuevo", async ({ page }) => {
    await page.goto("/suppliers");
    await expect(
      page.getByRole("heading", { name: /proveedor|supplier/i }),
    ).toBeVisible();
    // Empty state O tabla — uno de los dos debe estar
    const empty = page.getByTestId("suppliers-empty");
    const table = page.getByTestId("suppliers-table-root");
    await expect(empty.or(table)).toBeVisible({ timeout: 15000 });
  });

  test("crea supplier → aparece en lista → desactiva", async ({ page }) => {
    // Step 1: ir a "nuevo"
    await page.goto("/suppliers/new");
    await expect(page.getByTestId("supplier-form")).toBeVisible();

    // Step 2: rellenar form
    await page.getByLabel(/código|code/i).fill(TEST_SUPPLIER_CODE);
    await page.getByLabel(/nombre|name/i).first().fill(TEST_SUPPLIER_NAME);

    // Currency = EUR via Select
    await page.getByLabel(/moneda|currency/i).click();
    await page.getByRole("option", { name: "EUR" }).click();

    // Lead time = 7
    await page.getByLabel(/lead.*time|tiempo.*entrega/i).fill("7");

    // Step 3: submit
    await page.getByTestId("supplier-submit").click();

    // Toast OK
    await expect(
      page.getByText(/creado|created|guardad|saved/i).first(),
    ).toBeVisible({ timeout: 10000 });

    // Step 4: volver al listado y verificar
    await page.goto("/suppliers");
    await expect(page.getByTestId("suppliers-table-root")).toBeVisible({
      timeout: 10000,
    });
    await expect(
      page.getByTestId(`supplier-row-${TEST_SUPPLIER_CODE}`),
    ).toBeVisible();

    // Step 5: soft-deactivate via kebab menu
    // Buscar el actions menu por su patrón data-testid (supplier-actions-{id})
    const actionsButtons = page.locator('[data-testid^="supplier-actions-"]');
    await actionsButtons.first().click();
    await page.getByRole("menuitem", { name: /desactivar|deactivate/i }).click();
    await page.getByRole("button", { name: /confirmar|confirm/i }).click();

    await expect(
      page.getByText(/desactivad|deactivated/i).first(),
    ).toBeVisible({ timeout: 8000 });
  });
});
