/**
 * 09 — Dashboard KPIs (S3 wired) @critico.
 *
 * Verifica que `/dashboard` renderiza los 4 KPI cards con valores de
 * `/api/v1/dashboard/stats`. Mocks la respuesta vía route interception.
 *
 * Selectores: la página actual NO expone `data-testid` para los cards. Usamos
 * `getByText` con regex sobre los labels conocidos ("Cobertura traducción ES",
 * "Eventos audit 24 h", etc.).
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installDashboardMocks, FAKE_DASHBOARD } from "./fixtures/seed-extended";

test.describe("Pantalla Dashboard — KPIs S3 @critico", () => {
  test.beforeEach(async ({ page }) => {
    installDashboardMocks(page);
    await loginAsGerente(page);
  });

  test("renderiza los 4 KPI cards principales", async ({ page }) => {
    await page.goto("/dashboard");

    // Hero greeting con métricas inyectadas en texto
    await expect(
      page.getByText(/SKUs partial/i).first(),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText(/blocked/i).first(),
    ).toBeVisible();

    // KPI cards labels
    await expect(
      page.getByText(/Cobertura traducción ES/i),
    ).toBeVisible();
    await expect(
      page.getByText(/Cobertura traducción AR/i),
    ).toBeVisible();
    await expect(
      page.getByText(/SKUs partial \/ blocked/i),
    ).toBeVisible();
    await expect(
      page.getByText(/Eventos audit 24 h/i),
    ).toBeVisible();
  });

  test("KPI ES coverage muestra el porcentaje del mock", async ({ page }) => {
    await page.goto("/dashboard");
    const pct = `${Math.round(FAKE_DASHBOARD.translations.es_coverage_pct)}%`;
    // Buscamos el porcentaje renderizado dentro del card "Cobertura traducción ES"
    await expect(page.getByText(pct).first()).toBeVisible({ timeout: 10_000 });
  });

  test("calidad del catálogo muestra desglose Complete/Partial/Blocked", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page.getByText(/Calidad del catálogo/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/Complete/i).first()).toBeVisible();
    await expect(page.getByText(/Partial/i).first()).toBeVisible();
    await expect(page.getByText(/Blocked/i).first()).toBeVisible();
  });

  test("error state si stats falla → muestra MtError + retry", async ({
    page,
  }) => {
    // Sobrescribimos antes de navegar
    await page.route("**/api/v1/dashboard/stats", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "boom" }),
      });
    });
    await page.goto("/dashboard");
    await expect(
      page.getByText(/No se pudieron cargar los KPIs/i),
    ).toBeVisible({ timeout: 10_000 });
  });
});
