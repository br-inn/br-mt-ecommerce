/**
 * 17 — `/canales/amazon-uae` channel mirror diff + sync + publish @critico.
 *
 * Cubre:
 *  - Diff table renderiza con campos drift / match / missing
 *  - Botón Re-sync clickable (mock devuelve nuevo summary)
 *  - Botón "Publicar diferencias" habilitado solo si driftsCount > 0
 */

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installChannelMirrorMocks } from "./fixtures/seed-extended";

test.describe("Channel mirror Amazon UAE @critico", () => {
  test.beforeEach(async ({ page }) => {
    installChannelMirrorMocks(page);
    await loginAsGerente(page);
  });

  test("diff table renderiza con campos del seed (title, price_aed, description_ar)", async ({
    page,
  }) => {
    await page.goto("/canales/amazon-uae");
    await expect(
      page.getByText(/Channel mirror — Amazon UAE/i),
    ).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText(/title/i).first()).toBeVisible();
    await expect(page.getByText(/price_aed/i).first()).toBeVisible();
    await expect(page.getByText(/description_ar/i).first()).toBeVisible();
  });

  test("status pills aparecen (drift / sync / falta)", async ({ page }) => {
    await page.goto("/canales/amazon-uae");
    await expect(
      page.getByText(/Channel mirror/i),
    ).toBeVisible({ timeout: 15_000 });
    // Diferentes pills según estado: "drift", "sync", "falta en canal"
    await expect(page.getByText(/^drift$/i).first()).toBeVisible();
    await expect(page.getByText(/^sync$/i).first()).toBeVisible();
  });

  test("Re-sync dispara mutation y deja botón habilitado tras respuesta", async ({
    page,
  }) => {
    await page.goto("/canales/amazon-uae");
    const resync = page.getByRole("button", { name: /^Re-sync$/i });
    await expect(resync).toBeVisible({ timeout: 15_000 });
    await resync.click();
    await expect(resync).toBeEnabled({ timeout: 5_000 });
  });

  test("Publicar diferencias visible cuando hay drift", async ({ page }) => {
    await page.goto("/canales/amazon-uae");
    await expect(
      page.getByText(/Channel mirror/i),
    ).toBeVisible({ timeout: 15_000 });

    // El mock devuelve drift=2 missing=1 → driftsCount=3 → botón habilitado.
    const publish = page.getByRole("button", { name: /Publicar diferencias/i });
    await expect(publish).toBeVisible();
    await expect(publish).toBeEnabled();
  });
});
