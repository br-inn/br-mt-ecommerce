/**
 * 05 — Proveedores CRUD (Crítico).
 *
 * Flow happy-path (ruta canónica `/proveedores`):
 *  1. `/proveedores` carga (lista vacía o con data)
 *  2. Click "Nuevo" → form `/proveedores/nuevo`
 *  3. Rellenar code, name, currency=EUR, lead_time=7
 *  4. Submit → redirect al detalle + toast OK
 *  5. Volver al listado y verificar que aparece en la tabla
 *  6. Archivar (soft-delete) via menú de acciones
 *
 * Cleanup: el `installSuppliersMocks` mantiene el store en memoria; en modo
 * real (DB), el orquestador limpia con `seed_demo.py --reset-suppliers`.
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installSuppliersMocks } from "./fixtures/seed";

const TEST_SUPPLIER_CODE = `E2E_TEST_${Date.now()}`;
const TEST_SUPPLIER_NAME = "Proveedor E2E Test";

test.describe("Proveedores CRUD @critico", () => {
  test.beforeEach(async ({ page }) => {
    installSuppliersMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("listado vacío muestra estado empty + CTA nuevo", async ({ page }) => {
    await page.goto("/proveedores");
    await expect(
      page.getByRole("heading", { name: /proveedor|supplier/i }),
    ).toBeVisible();
    // Empty state O tabla — uno de los dos debe estar
    const empty = page.getByTestId("proveedores-empty");
    const table = page.getByTestId("proveedores-table-root");
    await expect(empty.or(table)).toBeVisible({ timeout: 15000 });
  });

  test("crea proveedor → aparece en lista → archiva", async ({ page }) => {
    // Step 1: ir a "nuevo"
    await page.goto("/proveedores/nuevo");
    await expect(page.getByTestId("proveedor-form")).toBeVisible();

    // Step 2: rellenar form (selectores por name= — el Label envuelve un div,
    // no el input, así que getByLabel no aplica).
    await page.locator('input[name="code"]').fill(TEST_SUPPLIER_CODE);
    await page.locator('input[name="name"]').fill(TEST_SUPPLIER_NAME);

    // Currency = EUR via Radix Select (role combobox)
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "EUR" }).click();

    // Lead time = 7
    await page.locator('input[name="lead_time_days"]').fill("7");

    // Step 3: submit
    await page.getByTestId("proveedor-submit").click();

    // Toast OK
    await expect(
      page.getByText(/creado|created|guardad|saved/i).first(),
    ).toBeVisible({ timeout: 10000 });

    // Step 4: volver al listado y verificar
    await page.goto("/proveedores");
    await expect(page.getByTestId("proveedores-table-root")).toBeVisible({
      timeout: 10000,
    });
    await expect(
      page.getByTestId(`proveedor-row-${TEST_SUPPLIER_CODE}`),
    ).toBeVisible();

    // Step 5: archivar (soft-delete) via kebab menu
    // Buscar el actions menu por su patrón data-testid (proveedor-actions-{code})
    const actionsButtons = page.locator('[data-testid^="proveedor-actions-"]');
    await actionsButtons.first().click();
    await page
      .getByRole("menuitem", { name: /archivar|archive|desactivar|deactivate/i })
      .click();
    await page.getByRole("button", { name: /confirmar|confirm/i }).click();

    await expect(
      page.getByText(/archivad|desactivad|deactivated/i).first(),
    ).toBeVisible({ timeout: 8000 });
  });
});
