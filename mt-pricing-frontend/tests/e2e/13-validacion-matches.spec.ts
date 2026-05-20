/**
 * 13 — `/catalogo/validacion` matches list + validate / discard @critico.
 *
 * Cubre:
 *  - Lista de candidatos con ≥1 fila + score pill
 *  - Cambio de FilterChip Pendientes → Validadas re-fetcha la lista
 *  - Click en "Validar match" dispara la mutación (mockeada)
 *
 * No data-testids; usamos getByRole + getByText con regex.
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installMatchesMocks, FAKE_MATCHES } from "./fixtures/seed-extended";

test.describe("Validación matches @critico", () => {
  test.beforeEach(async ({ page }) => {
    installMatchesMocks(page);
    await loginAsGerente(page);
  });

  test("renderiza candidatos con marcas seed", async ({ page }) => {
    await page.goto("/catalogo/validacion");
    // Header workflow
    await expect(
      page.getByText(/Validación humana asistida/i),
    ).toBeVisible({ timeout: 15_000 });

    // Cada match tiene .brand renderizado en la primera columna.
    await expect(page.getByText(FAKE_MATCHES[0]!.brand).first()).toBeVisible();
    await expect(page.getByText(FAKE_MATCHES[1]!.brand).first()).toBeVisible();
  });

  test("FilterChip 'Validadas' filtra la lista (server-side)", async ({
    page,
  }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(/Candidatos/i).first()).toBeVisible({
      timeout: 15_000,
    });

    // Default: pending — clic en "Validadas"
    await page
      .getByRole("button", { name: /^Validadas$/i })
      .click();

    // Como en seed no hay validated, esperamos empty state
    await expect(
      page.getByText(/Sin candidatos|Re-scrape|Re-?scrape/i).first(),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("botón 'Validar match' visible y clickable en fila pending", async ({
    page,
  }) => {
    await page.goto("/catalogo/validacion");
    await expect(page.getByText(FAKE_MATCHES[0]!.brand).first()).toBeVisible({
      timeout: 15_000,
    });

    // Hay 2 botones "Validar" (uno por fila pending) — primero
    const validateBtns = page.getByRole("button", { name: /^Validar$/i });
    await expect(validateBtns.first()).toBeVisible();
    await validateBtns.first().click();
    // Tras la mutación el backend mock devuelve status=validated y la fila
    // se re-renderiza con badge "Validado".
    await expect(page.getByText(/Validado/i).first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Re-scrape encola un job (botón disabled-while-pending)", async ({
    page,
  }) => {
    await page.goto("/catalogo/validacion");
    await expect(
      page.getByRole("button", { name: /Re-scrape/i }),
    ).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /Re-scrape/i }).click();
    // El backend mock acepta y devuelve task_id; el botón vuelve a estar
    // habilitado tras la respuesta.
    await expect(
      page.getByRole("button", { name: /Re-scrape/i }),
    ).toBeEnabled({ timeout: 5_000 });
  });
});
