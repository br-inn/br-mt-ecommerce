/**
 * 02 — Auth: Login Magic Link + Password (Crítico).
 *
 * Magic Link: NO podemos completar el OTP sin email real → solo verificamos
 * que el form renderiza, el submit dispara `signInWithOtp` y aparece el toast
 * de éxito (mock o real).
 *
 * Password: bypass via `installAuthMocks` o cuenta seed real (orquestador
 * puede crear cuenta vía Supabase admin).
 */

import { expect, test } from "@playwright/test";
import { installAuthMocks, loginAsRole } from "./fixtures/auth";
import { E2E_USER_EMAIL } from "./fixtures/env";

test.describe("Auth — login flows @critico", () => {
  test("guest is redirected from /dashboard → /login", async ({ page }) => {
    installAuthMocks(page, "gerente");
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading")).toBeVisible();
  });

  test("magic link form submits and shows confirmation toast", async ({
    page,
  }) => {
    installAuthMocks(page, "gerente");
    await page.goto("/login");

    await page.getByLabel(/correo|email/i).fill(E2E_USER_EMAIL);
    await page.getByRole("button", { name: /enlace|magic/i }).click();

    // Sonner toast: ES "enlace" / EN "sign-in link"
    await expect(
      page.getByText(/enlace|sign-?in link|magic link/i).first(),
    ).toBeVisible({ timeout: 8000 });
  });

  test("password login → /dashboard + user menu visible", async ({ page }) => {
    await loginAsRole(page, "gerente");
    await expect(page.getByTestId("user-menu-trigger")).toBeVisible();
  });

  test("user menu signout → returns to /login", async ({ page }) => {
    await loginAsRole(page, "gerente");
    await page.getByTestId("user-menu-trigger").click();
    await expect(page.getByText(E2E_USER_EMAIL)).toBeVisible();
    await page.getByTestId("user-menu-signout").click();
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });
});
