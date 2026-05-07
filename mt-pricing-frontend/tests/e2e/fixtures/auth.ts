/**
 * Helpers de autenticación para E2E.
 *
 * Estrategia (en orden de preferencia):
 *  1. Si `E2E_USER_PASSWORD` está set en el env, login real via password
 *     (Supabase signInWithPassword) — flujo más cercano a producción y más
 *     resiliente.
 *  2. Si Supabase admin keys disponibles (`SUPABASE_URL` +
 *     `SUPABASE_SERVICE_ROLE_KEY`), creamos sesión vía admin API y seteamos
 *     cookie SSR directamente (más rápido, no UI clicks).
 *  3. Fallback: mocks `route()` clásicos (compatibles con `auth.spec.ts`).
 *
 * Magic Link NO se completa automáticamente — requeriría leer email real. El
 * test de login con magic-link solo verifica que el endpoint dispara el OTP y
 * el toast aparece (signInWithOtp mockeado).
 */

import { expect, type Page } from "@playwright/test";
import {
  E2E_USER_EMAIL,
  E2E_USER_PASSWORD,
  USE_REAL_SUPABASE,
} from "./env";

const FAKE_USER_ID = "11111111-1111-1111-1111-111111111111";
const FAKE_ACCESS_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature";

export type RoleCode = "comercial" | "gerente" | "ti" | "admin";

interface RoleProfile {
  code: RoleCode;
  name: string;
  permissions: string[];
}

const ROLE_PERMISSIONS: Record<RoleCode, RoleProfile> = {
  comercial: {
    code: "comercial",
    name: "Comercial",
    permissions: ["products:read", "prices:propose"],
  },
  gerente: {
    code: "gerente",
    name: "Gerente",
    permissions: [
      "products:read",
      "products:write",
      "products:delete",
      "suppliers:read",
      "suppliers:write",
      "suppliers:delete",
      "translations:approve",
      "imports:execute",
      "prices:approve",
    ],
  },
  ti: {
    code: "ti",
    name: "TI",
    permissions: ["products:read", "users:manage", "audit:read"],
  },
  admin: {
    code: "admin",
    name: "Admin",
    permissions: [
      "products:read",
      "products:write",
      "products:delete",
      "suppliers:read",
      "suppliers:write",
      "suppliers:delete",
      "imports:execute",
      "users:manage",
      "audit:read",
    ],
  },
};

/**
 * Instala mocks de Supabase auth + backend `/api/v1/me` para una página dada.
 * Solo aplica si NO usamos Supabase real.
 */
export function installAuthMocks(page: Page, role: RoleCode = "gerente"): void {
  if (USE_REAL_SUPABASE) return;

  const profile = ROLE_PERMISSIONS[role];

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
          email: E2E_USER_EMAIL,
          app_metadata: {},
          user_metadata: { full_name: "E2E User" },
        },
      }),
    });
  });

  page.route("**/auth/v1/otp**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  page.route("**/auth/v1/user**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: E2E_USER_EMAIL,
        user_metadata: { full_name: "E2E User" },
      }),
    });
  });

  page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: FAKE_USER_ID,
        email: E2E_USER_EMAIL,
        full_name: "E2E User",
        avatar_url: null,
        locale: "es",
        is_active: true,
        role: {
          id: "22222222-2222-2222-2222-222222222222",
          code: profile.code,
          name: profile.name,
        },
        last_login_at: null,
        created_at: new Date().toISOString(),
        permissions: profile.permissions,
      }),
    });
  });
}

/**
 * Login flow vía UI (modo password). Mantiene la cookie SSR en el contexto.
 * Si `installAuthMocks` se llamó previamente, el flow es 100% mock.
 */
export async function loginAsRole(
  page: Page,
  role: RoleCode = "gerente",
): Promise<void> {
  installAuthMocks(page, role);
  await page.goto("/login");
  // Toggle hacia password mode
  await page
    .getByRole("button", { name: /usar contraseña|use password/i })
    .click();
  await page.getByLabel(/correo|email/i).fill(E2E_USER_EMAIL);
  await page.getByLabel(/contraseña|password/i).fill(E2E_USER_PASSWORD);
  await page.getByRole("button", { name: /entrar|sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
}
