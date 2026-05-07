/**
 * 04 — Pantalla 3 + Pantalla 4 — Product detail + edit + Imágenes (Crítico).
 *
 * Cubre:
 *  - Header con SKU + name + back link
 *  - Tab "Ficha técnica" visible por defecto
 *  - Click "Editar" → form aparece → cambiar `name_en` → submit → toast OK
 *  - Cambio a tab "Imágenes" → drop zone visible
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installProductsMocks, FAKE_PRODUCTS } from "./fixtures/seed";

const SKU = FAKE_PRODUCTS[0]!.sku;

test.describe("Pantallas 3 + 4 — product detail/edit/images @critico", () => {
  test.beforeEach(async ({ page }) => {
    installProductsMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("renderiza header + back link + tab Ficha técnica", async ({ page }) => {
    await page.goto(`/products/${SKU}`);
    await expect(page.getByTestId("product-detail-root")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(SKU).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /volver|back/i })).toBeVisible();
    await expect(page.getByTestId("tab-specs")).toBeVisible();
    await expect(page.getByTestId("product-specs")).toBeVisible();
  });

  test("editar identidad → cambiar name_en → guardar → toast OK", async ({
    page,
  }) => {
    await page.goto(`/products/${SKU}`);
    await expect(page.getByTestId("product-detail-root")).toBeVisible();

    await page.getByTestId("product-edit-toggle").click();
    await expect(page.getByTestId("product-edit-form")).toBeVisible();

    // Cambiar name_en — input dentro del form
    const nameInput = page
      .getByTestId("product-edit-form")
      .getByLabel(/name.*en|nombre.*en/i)
      .first();
    await nameInput.fill("Valve DN50 PN16 — edited by E2E");

    await page.getByTestId("product-edit-submit").click();

    // Toast sonner — buscar texto de éxito (es: "actualizado", en: "updated"/"saved")
    await expect(
      page.getByText(/actualiz|updated|saved|guardad/i).first(),
    ).toBeVisible({ timeout: 8000 });
  });

  test("tab Imágenes → drop zone visible", async ({ page }) => {
    await page.goto(`/products/${SKU}`);
    await expect(page.getByTestId("product-detail-root")).toBeVisible();

    await page.getByTestId("tab-images").click();
    await expect(page.getByTestId("product-images-tab")).toBeVisible();
    // El uploader (drop zone) debe aparecer dentro del tab
    await expect(page.getByTestId("images-uploader")).toBeVisible({
      timeout: 5000,
    });
  });
});
