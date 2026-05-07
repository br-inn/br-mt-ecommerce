/**
 * 18 — `/admin/divisas` + `/admin/fx-rates` @secundario.
 *
 * Cubre:
 *  - `/admin/divisas` lista currencies seed (EUR, AED, USD)
 *  - `/admin/divisas` lista FX rates con badge "Vigente" para rate sin
 *    effective_to
 *  - `/admin/fx-rates` panel admin S3 carga sin error
 */

import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers/auth-as-role";
import { installCurrencyAndFxMocks } from "./fixtures/seed-extended";

test.describe("Admin — divisas + fx-rates @secundario", () => {
  test.beforeEach(async ({ page }) => {
    installCurrencyAndFxMocks(page);
    await loginAsAdmin(page);
  });

  test("/admin/divisas: lista currencies seed (EUR, AED, USD)", async ({
    page,
  }) => {
    await page.goto("/admin/divisas");

    // Esperamos los códigos en celdas mono-fonted
    await expect(page.getByText("EUR").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("AED").first()).toBeVisible();
    await expect(page.getByText("USD").first()).toBeVisible();
  });

  test("/admin/divisas: rate vigente con badge", async ({ page }) => {
    await page.goto("/admin/divisas");
    // El mock devuelve un rate con effective_to=null → badge "Vigente"/"Current"
    await expect(
      page.getByText(/vigente|current/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("/admin/fx-rates: client S3 carga sin MtError", async ({ page }) => {
    await page.goto("/admin/fx-rates");
    // El page.tsx wrappea <FxRatesAdminClient /> que muestra Filtros from/to
    // y la tabla con rates seed.
    await expect(
      page.getByText("EUR").first(),
    ).toBeVisible({ timeout: 15_000 });
    // No debe haber error toast ni MtError
    await expect(page.getByText(/load failed|error/i)).toHaveCount(0, {
      timeout: 2_000,
    });
  });
});
