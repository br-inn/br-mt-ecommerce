/**
 * Helper para loguear con un rol específico (comercial/gerente/ti/admin).
 *
 * Wrapper sobre `installAuthMocks` + `loginAsRole` que evita repetir el
 * boilerplate de mocks en cada describe. NO modifica las fixtures originales
 * — sólo encapsula el patrón canónico.
 *
 * Uso:
 *   test.beforeEach(async ({ page }) => {
 *     await loginAsGerente(page);
 *   });
 */

import type { Page } from "@playwright/test";
import { loginAsRole, type RoleCode } from "../fixtures/auth";

export async function loginAs(page: Page, role: RoleCode): Promise<void> {
  await loginAsRole(page, role);
}

export async function loginAsGerente(page: Page): Promise<void> {
  await loginAsRole(page, "gerente");
}

export async function loginAsComercial(page: Page): Promise<void> {
  await loginAsRole(page, "comercial");
}

export async function loginAsTI(page: Page): Promise<void> {
  await loginAsRole(page, "ti");
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await loginAsRole(page, "admin");
}
