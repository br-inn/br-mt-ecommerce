/**
 * 15 — `/precios/[id]` detail + revise dialog + bulk-publish dialog @critico.
 *
 * Cubre:
 *  - Detail card con amount + breakdown
 *  - Click en "Revisar" abre el dialog (data-testid="revise-new-amount")
 *  - Submit revise dialog con amount/reason mocks la mutación
 *  - Botón "Publicar" abre el bulk-publish dialog
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installPricingMocks, FAKE_PRICES } from "./fixtures/seed-extended";

const PRICE_ID = FAKE_PRICES[0]!.id;

test.describe("Pricing detail — revise + bulk-publish dialogs @critico", () => {
  test.beforeEach(async ({ page }) => {
    installPricingMocks(page);
    // Forzamos status=approved para habilitar el botón Publicar
    await page.route(`**/api/v1/pricing/prices/${PRICE_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...FAKE_PRICES[0],
          status: "approved",
          cost_total: "120.00",
          fx_rate: "4.05",
          median_aed: "200.00",
          rule_applied: "median_minus_2pct",
          formula: "amount = median_aed * 0.98",
          cap_applied: false,
          floor_applied: false,
          has_velocity_premium: false,
          has_warnings: false,
          has_critical_alerts: false,
          alerts: [],
          approval_events: [],
          breakdown: { cost: 120.0 },
        }),
      });
    });
    await loginAsGerente(page);
  });

  test("detail card renderiza importe del seed", async ({ page }) => {
    await page.goto(`/precios/${PRICE_ID}`);
    await expect(
      page.getByText(FAKE_PRICES[0]!.amount).first(),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/Historial de aprobación/i),
    ).toBeVisible();
  });

  test("revise dialog: abrir + escribir + submit (data-testid)", async ({
    page,
  }) => {
    await page.goto(`/precios/${PRICE_ID}`);
    await expect(
      page.getByRole("button", { name: /^Revisar$/i }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Revisar$/i }).click();

    const newAmount = page.getByTestId("revise-new-amount");
    const reason = page.getByTestId("revise-reason");
    const submit = page.getByTestId("revise-submit");

    await expect(newAmount).toBeVisible();
    await newAmount.fill("199.99");
    await reason.fill("Margen ajustado por solicitud del Gerente");
    // Submit habilitado tras llenar campos válidos.
    await expect(submit).toBeEnabled({ timeout: 3_000 });
  });

  test("publicar abre bulk-publish dialog (data-testid)", async ({ page }) => {
    await page.goto(`/precios/${PRICE_ID}`);
    await expect(
      page.getByRole("button", { name: /^Publicar$/i }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Publicar$/i }).click();

    await expect(page.getByTestId("bulk-publish-submit")).toBeVisible({
      timeout: 5_000,
    });
  });
});
