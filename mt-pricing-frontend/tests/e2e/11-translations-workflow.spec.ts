/**
 * 11 — Traducciones workflow `/catalogo/[sku]/traducciones` @critico.
 *
 * Cubre:
 *  - Carga el detail con tres cards (canonical EN, ES, AR).
 *  - Botones de workflow (Guardar borrador / Solicitar revisión / Aprobar)
 *    presentes según permisos del rol gerente.
 *  - El form AR tiene `dir="rtl"` aplicado.
 *
 * Selectores: la página usa shadcn `Card` + `Button`. Usamos `getByRole`
 * sobre los headings y los botones de acción. NO data-testids específicos.
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installTranslationsMocks } from "./fixtures/seed-extended";

const SKU = "MTV-1004";

test.describe("Traducciones — workflow buttons + RTL @critico", () => {
  test.beforeEach(async ({ page }) => {
    installTranslationsMocks(page, SKU);
    await loginAsGerente(page);
  });

  test("renderiza los 3 cards (EN canonical, ES, AR)", async ({ page }) => {
    await page.goto(`/catalogo/${SKU}/traducciones`);
    // ProductHeader carga primero — esperamos el SKU en algún lugar.
    await expect(page.getByText(SKU).first()).toBeVisible({ timeout: 15_000 });

    // Esperamos al menos un Card con label "name" / inputs presentes.
    // Hay 2 forms (es + ar) cada uno con su input "name-es"/"name-ar".
    await expect(page.locator("#name-es")).toBeVisible();
    await expect(page.locator("#name-ar")).toBeVisible();
  });

  test("form AR tiene dir=rtl aplicado al wrapper", async ({ page }) => {
    await page.goto(`/catalogo/${SKU}/traducciones`);
    await expect(page.locator("#name-ar")).toBeVisible({ timeout: 15_000 });

    // El input AR tiene atributo dir="rtl" (lang="ar" → dir="rtl" en el form)
    const dirAttr = await page.locator("#name-ar").getAttribute("dir");
    expect(dirAttr).toBe("rtl");
    const dirEs = await page.locator("#name-es").getAttribute("dir");
    expect(dirEs).toBe("ltr");
  });

  test("botones de workflow visibles para rol gerente (translations:approve)", async ({
    page,
  }) => {
    await page.goto(`/catalogo/${SKU}/traducciones`);
    await expect(page.locator("#name-es")).toBeVisible({ timeout: 15_000 });

    // Esperamos al menos un botón "Aprobar" + "Solicitar" + "Guardar borrador".
    // Como hay 2 forms, usamos `.first()` para no dudar de cardinalidad.
    await expect(
      page.getByRole("button", { name: /aprobar|approve/i }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /solicitar|request/i }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /guardar borrador|save draft/i }).first(),
    ).toBeVisible();
  });
});
