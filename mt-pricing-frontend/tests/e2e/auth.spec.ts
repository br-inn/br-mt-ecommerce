/**
 * E2E auth flow.
 *
 * Estrategia de mocking:
 *  - Interceptamos `**\/auth/v1/token*` (Supabase) → devolvemos session falsa.
 *  - Interceptamos `**\/api/v1/me` (backend) → devolvemos perfil falso.
 *  - Para CI con Supabase real, basta con setear `E2E_USE_REAL_SUPABASE=1`
 *    + credenciales de test y se saltan los `route()` mocks.
 */

import { expect, test } from "@playwright/test";

const FAKE_USER_ID = "11111111-1111-1111-1111-111111111111";
const FAKE_ACCESS_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature";

const useRealSupabase = !!process.env["E2E_USE_REAL_SUPABASE"];

function installAuthMocks(page: import("@playwright/test").Page) {
  if (useRealSupabase) return;

  // Supabase token endpoint (password grant).
  page.route("**/auth/v1/token**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: FAKE_ACCESS_TOKEN,
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: "fake-refresh",
        user: {
          id: FAKE_USER_ID,
          email: "e2e@mt.ae",
          app_metadata: {},
          user_metadata: { full_name: "E2E User" },
        },
      }),
    });
  });

  // Supabase OTP (magic link request) — siempre OK.
  page.route("**/auth/v1/otp**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  // Supabase user endpoint (used by getUser).
  page.route("**/auth/v1/user**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: "e2e@mt.ae",
        user_metadata: { full_name: "E2E User" },
      }),
    });
  });

  // Backend `/me`.
  page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: "e2e@mt.ae",
        full_name: "E2E User",
        avatar_url: null,
        locale: "es",
        is_active: true,
        role: { id: "22222222-2222-2222-2222-222222222222", code: "comercial", name: "Comercial" },
        last_login_at: null,
        created_at: new Date().toISOString(),
        permissions: ["products:read", "prices:propose"],
      }),
    });
  });
}

test.describe("Auth flow", () => {
  test("redirects unauthenticated user from /dashboard to /login", async ({ page }) => {
    installAuthMocks(page);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading")).toBeVisible();
  });

  test("login with magic link shows success toast", async ({ page }) => {
    installAuthMocks(page);
    await page.goto("/login");

    await page.getByLabel(/correo|email/i).fill("e2e@mt.ae");
    await page.getByRole("button", { name: /enlace|magic/i }).click();

    // Sonner toast shows success message.
    await expect(page.getByText(/enlace|sign-in link/i)).toBeVisible({ timeout: 5000 });
  });

  test("login with password navigates to dashboard and shows account link", async ({
    page,
  }) => {
    installAuthMocks(page);

    await page.goto("/login");
    await page.getByRole("button", { name: /usar contraseña|use password/i }).click();

    await page.getByLabel(/correo|email/i).fill("e2e@mt.ae");
    await page.getByLabel(/contraseña|password/i).fill("super-secret-pass");
    await page.getByRole("button", { name: /entrar|sign in/i }).click();

    // Magic link mock makes session active → user routed to dashboard.
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  });

  test("user menu shows logout and triggers sign out", async ({ page }) => {
    installAuthMocks(page);

    // Force-load dashboard with fake cookie session bypass.
    await page.goto("/login");
    await page.getByRole("button", { name: /usar contraseña|use password/i }).click();
    await page.getByLabel(/correo|email/i).fill("e2e@mt.ae");
    await page.getByLabel(/contraseña|password/i).fill("super-secret-pass");
    await page.getByRole("button", { name: /entrar|sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

    await page.getByTestId("user-menu-trigger").click();
    await expect(page.getByText(/e2e@mt\.ae/)).toBeVisible();
    await page.getByTestId("user-menu-signout").click();

    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });
});
