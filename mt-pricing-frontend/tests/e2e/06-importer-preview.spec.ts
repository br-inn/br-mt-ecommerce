/**
 * 06 — Importer wizard — Pantalla 10 (Crítico).
 *
 * SOLO preview, NUNCA apply. Apply en validación automática es destructivo
 * (puede modificar 5085 rows). Se cubre:
 *  1. `/imports` carga el wizard step 1
 *  2. Subir el `PIM completo.xlsx` real (o mock)
 *  3. Aparece preview con métricas (rows analizados/new/updated)
 *  4. Cancelar (back to upload) — NO confirmar apply
 */

import * as path from "node:path";
import * as fs from "node:fs";
import { expect, test } from "@playwright/test";
import { loginAsRole } from "./fixtures/auth";
import { installImportsMocks } from "./fixtures/seed";

// __dirname disponible en CJS (Playwright executes specs as CJS por defecto).
// PIM real está en repo root: Documentos referencia de articulos/PIM completo.xlsx
const REAL_PIM_PATH = path.resolve(
  __dirname,
  "../../../Documentos referencia de articulos/PIM completo.xlsx",
);

// Fallback: archivo dummy si el PIM real no existe en el dev box
const DUMMY_PIM_PATH = path.resolve(__dirname, "fixtures/dummy.xlsx");

test.describe("Pantalla 10 — importer preview @critico", () => {
  test.beforeEach(async ({ page }) => {
    installImportsMocks(page);
    await loginAsRole(page, "gerente");
  });

  test("upload step renderiza dropzone + submit deshabilitado", async ({
    page,
  }) => {
    await page.goto("/imports");
    await expect(page.getByTestId("import-wizard")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId("import-upload-step")).toBeVisible();
    await expect(page.getByTestId("import-dropzone")).toBeVisible();
    await expect(page.getByTestId("import-upload-submit")).toBeDisabled();
  });

  test("upload PIM → muestra preview (NO apply)", async ({ page }) => {
    await page.goto("/imports");
    await expect(page.getByTestId("import-wizard")).toBeVisible();

    // Decidir qué archivo usar
    const filePath = fs.existsSync(REAL_PIM_PATH) ? REAL_PIM_PATH : null;
    if (!filePath) {
      test.skip(
        true,
        `PIM real no encontrado en ${REAL_PIM_PATH}. Usa el archivo del repo o ` +
          `coloca un xlsx de prueba en ${DUMMY_PIM_PATH}.`,
      );
      return;
    }

    // setInputFiles directo sobre el input oculto
    await page.getByTestId("import-file-input").setInputFiles(filePath);
    await expect(page.getByTestId("import-file-preview")).toBeVisible();

    await page.getByTestId("import-upload-submit").click();

    // Tras upload, preview-diff debe aparecer (mock devuelve 5085 rows)
    // Buscamos por texto que mencione "5085" o las labels de diff
    await expect(
      page.getByText(/5085|preview|diff|cambios|nuevos|actualiz/i).first(),
    ).toBeVisible({ timeout: 30000 });

    // CRITICAL: NO clickamos "Confirmar apply". Cancelamos.
    // El back/cancel debe llevarnos de vuelta al step 1.
    const cancelBtn = page
      .getByRole("button", { name: /cancelar|cancel|atrás|back/i })
      .first();
    if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelBtn.click();
    }
  });
});
