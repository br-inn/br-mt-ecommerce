/**
 * 07 — i18n locale switcher (Crítico).
 *
 * Verifica:
 *  - Topbar muestra el dropdown de idioma con badge ES/EN
 *  - Click en switcher → menu con ambas opciones
 *  - Cambiar a EN → la cookie `mt-locale` se setea
 *  - Recargar y comprobar que la UI sigue en EN
 */

import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";

test.describe("i18n switcher topbar @critico", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRole(page, "gerente");
  });

  test("ES → EN persiste cookie mt-locale", async ({ page, context }) => {
    await page.goto("/dashboard");

    const switcher = page.getByTestId("locale-switcher-trigger");
    await expect(switcher).toBeVisible();

    // Estado inicial — leer texto del badge
    const initialBadge = (await switcher.textContent())?.toUpperCase() ?? "";

    await switcher.click();
    // Ambas opciones deben estar
    await expect(page.getByTestId("locale-switcher-item-es")).toBeVisible();
    await expect(page.getByTestId("locale-switcher-item-en")).toBeVisible();

    // Pickear el opuesto
    const targetLocale = initialBadge.includes("ES") ? "en" : "es";
    await page.getByTestId(`locale-switcher-item-${targetLocale}`).click();

    // Cookie mt-locale debe reflejar el cambio
    await expect
      .poll(
        async () => {
          const cookies = await context.cookies();
          const c = cookies.find((c) => c.name === "mt-locale");
          return c?.value;
        },
        { timeout: 5000 },
      )
      .toBe(targetLocale);

    // Tras refresh, switcher mantiene el nuevo estado
    await page.reload();
    await expect(switcher).toContainText(targetLocale.toUpperCase(), {
      timeout: 5000,
    });
  });
});
