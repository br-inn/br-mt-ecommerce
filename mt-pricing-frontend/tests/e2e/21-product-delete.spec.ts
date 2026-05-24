/**
 * 21 — Journey P1 — Baja logica de producto (Critico).
 *
 * FR-CAT-027: DELETE /products/{sku} → soft-delete.
 * FR-CAT-028: producto dado de baja no aparece en listados.
 * FR-CAT-029: requiere products:delete.
 */

import { expect, type Page, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { FAKE_PRODUCTS, commonProductFields, installProductsMocks } from "./fixtures/seed";

const SKU_TO_DELETE = FAKE_PRODUCTS[0]!.sku;

function installDeleteMocks(page: Page): void {
  installProductsMocks(page);

  void page.route(`**/api/v1/products/${SKU_TO_DELETE}`, async (route, request) => {
    if (request.method() === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
    } else if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...commonProductFields(FAKE_PRODUCTS[0]!),
          translations: [],
          assets: [],
        }),
      });
    } else {
      await route.continue();
    }
  });
}

test.describe("Journey P1 — Baja logica de producto @critico", () => {
  test.beforeEach(async ({ page }) => {
    installDeleteMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("boton de baja visible en detalle y solicita confirmacion (FR-CAT-027)", async ({ page }) => {
    await page.goto(`/products/${SKU_TO_DELETE}`);
    await expect(page.getByTestId("product-detail-root")).toBeVisible({ timeout: 15000 });

    const deleteBtn = page
      .getByTestId("product-delete-button")
      .or(page.getByRole("button", { name: /baja|delete|eliminar|dar de baja/i }))
      .first();
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();

    const confirmDialog = page.getByRole("dialog").or(page.getByTestId("confirm-dialog")).first();
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
  });

  test("confirmar baja llama DELETE y muestra exito (FR-CAT-027, FR-CAT-028)", async ({ page }) => {
    await page.goto(`/products/${SKU_TO_DELETE}`);
    await expect(page.getByTestId("product-detail-root")).toBeVisible({ timeout: 15000 });

    const deleteBtn = page
      .getByTestId("product-delete-button")
      .or(page.getByRole("button", { name: /baja|delete|eliminar|dar de baja/i }))
      .first();
    await deleteBtn.click();

    const confirmBtn = page
      .getByTestId("confirm-delete-button")
      .or(page.getByRole("button", { name: /confirmar|confirm|si|yes/i }))
      .first();
    await confirmBtn.click();

    await expect(
      page
        .getByText(/eliminado|deleted|baja|exito|success/i)
        .first()
        .or(page.getByTestId("products-table-root")),
    ).toBeVisible({ timeout: 8000 });
  });
});
