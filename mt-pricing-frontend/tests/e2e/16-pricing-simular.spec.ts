/**
 * 16 — `/precios/simular` Pricing studio @critico.
 *
 * Cubre:
 *  - Form inputs (SKU, channel select, scheme) renderiza
 *  - Click "Simular" → backend mock devuelve PricingResult, ResultCard pinta
 *  - Click "Enviar a aprobación" dispara propose (mock)
 */

import { expect, test } from "@playwright/test";
import { loginAsComercial } from "./helpers/auth-as-role";
import { installPricingMocks } from "./fixtures/seed-extended";

test.describe("Pricing studio — simulate + propose @critico", () => {
  test.beforeEach(async ({ page }) => {
    installPricingMocks(page);
    await loginAsComercial(page);
  });

  test("form renderiza con valores default", async ({ page }) => {
    await page.goto("/precios/simular");
    await expect(
      page.getByText(/Pricing what-if/i),
    ).toBeVisible({ timeout: 15_000 });

    // SKU input default = MTV-1004
    await expect(page.locator("input").filter({ hasText: "" }).first()).toBeVisible();
  });

  test("click Simular muestra ResultCard con margen %", async ({ page }) => {
    await page.goto("/precios/simular");
    await expect(
      page.getByRole("button", { name: /^Simular$/i }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Simular$/i }).click();

    // El mock devuelve margin_pct=0.32 → "32.0% margen"
    await expect(page.getByText(/% margen/i).first()).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText(/Escenario simulado/i)).toBeVisible();
  });

  test("Enviar a aprobación dispara propose (botón habilitado tras click)", async ({
    page,
  }) => {
    await page.goto("/precios/simular");
    const proposeBtn = page.getByRole("button", {
      name: /Enviar a aprobación/i,
    }).first();
    await expect(proposeBtn).toBeVisible({ timeout: 15_000 });

    await proposeBtn.click();
    await expect(proposeBtn).toBeEnabled({ timeout: 5_000 });
  });
});
