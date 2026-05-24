/**
 * 20 — Journey P1 — Alta de producto (Critico).
 *
 * FR-CAT-001: POST /products con datos validos → producto creado.
 * FR-CAT-002: data_quality='partial' por defecto en producto nuevo.
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installProductsMocks } from "./fixtures/seed";

const NEW_SKU = "NEW-VAL-E2E-20";
const NEW_NAME = "Playwright Created Valve DN25";

test.describe("Journey P1 — Alta de producto @critico", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);

    void page.route("**/api/v1/products", async (route, request) => {
      if (request.method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            sku: NEW_SKU,
            name_en: NEW_NAME,
            family: "valves_ball",
            brand: "MT",
            data_quality: "partial",
            lifecycle_status: "active",
            translations: [],
            assets: [],
          }),
        });
      } else {
        await route.continue();
      }
    });

    await loginAsRole(page, "gerente");
  });

  test("formulario de alta visible y envio crea el producto (FR-CAT-001)", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible({ timeout: 15000 });

    const createBtn = page
      .getByTestId("product-create-button")
      .or(page.getByRole("button", { name: /nuevo|create|add/i }));
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    const form = page
      .getByTestId("product-create-form")
      .or(page.getByRole("dialog"))
      .first();
    await expect(form).toBeVisible({ timeout: 5000 });

    await form.getByLabel(/sku/i).fill(NEW_SKU);
    await form.getByLabel(/name.*en|nombre.*en/i).fill(NEW_NAME);
    await form.getByRole("button", { name: /crear|guardar|save|submit/i }).click();

    await expect(
      page.getByText(/creado|created|exito|success/i).first(),
    ).toBeVisible({ timeout: 8000 });
  });

  test("formulario rechaza SKU vacio (validacion client-side)", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByTestId("products-table-root")).toBeVisible({ timeout: 15000 });

    const createBtn = page
      .getByTestId("product-create-button")
      .or(page.getByRole("button", { name: /nuevo|create|add/i }));
    await createBtn.click();

    const form = page
      .getByTestId("product-create-form")
      .or(page.getByRole("dialog"))
      .first();
    await expect(form).toBeVisible();

    await form.getByRole("button", { name: /crear|guardar|save|submit/i }).click();

    await expect(
      page.getByText(/requerido|required|obligatorio/i).first(),
    ).toBeVisible({ timeout: 3000 });
  });
});
