/**
 * 12 — Datasheets uploader `/catalogo/[sku]/datasheets` @critico.
 *
 * Cubre:
 *  - Lista vacía + dropzone visible
 *  - Upload de PDF dummy → muestra preview (botón "Aplicar") sin commit real
 *  - Apply opcional skipped si no hay backend (depende de `MT_LIVE_NETWORK`)
 *
 * Selectores notables exportados por el frontend:
 *  - data-testid="datasheets-dropzone"
 *  - data-testid="datasheets-submit-preview"
 *  - data-testid="datasheets-apply"
 */

import * as path from "node:path";
import * as fs from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";
import { installDatasheetsMocks } from "./fixtures/seed-extended";

const SKU = "MTV-1004";
const TMP_PDF = path.resolve(__dirname, "fixtures", "dummy-datasheet.pdf");
const LIVE = process.env["MT_LIVE_NETWORK"] === "1";

async function ensureDummyPdf(): Promise<string> {
  // Genera un PDF mínimo válido (solo header) si no existe — suficiente para
  // que el dropzone lo acepte; el backend mockeado no lo procesa.
  try {
    await fs.access(TMP_PDF);
    return TMP_PDF;
  } catch {
    const minimal =
      "%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n";
    await fs.writeFile(TMP_PDF, minimal, "utf8");
    return TMP_PDF;
  }
}

test.describe("Datasheets — uploader @critico", () => {
  test.beforeEach(async ({ page }) => {
    installDatasheetsMocks(page, SKU);
    await loginAsGerente(page);
  });

  test("dropzone visible + lista vacía render", async ({ page }) => {
    await page.goto(`/catalogo/${SKU}/datasheets`);
    await expect(page.getByTestId("datasheets-dropzone")).toBeVisible({
      timeout: 15_000,
    });
    // Empty state de la lista
    await expect(page.getByText(/Sin datasheets/i)).toBeVisible();
  });

  test("subir PDF dummy → preview con botón apply (no aplica)", async ({
    page,
  }) => {
    test.skip(LIVE, "Live network: subida real no determinística sin orquestador");
    const filePath = await ensureDummyPdf();
    await page.goto(`/catalogo/${SKU}/datasheets`);
    await expect(page.getByTestId("datasheets-dropzone")).toBeVisible();

    // El uploader expone un input file dentro del dropzone.
    const fileInput = page.locator("input[type='file']").first();
    await fileInput.setInputFiles(filePath);

    // Submit preview
    await page.getByTestId("datasheets-submit-preview").click();

    // Apply visible — pero NO lo cliqueamos (S4 backend puede persistir).
    await expect(page.getByTestId("datasheets-apply")).toBeVisible({
      timeout: 15_000,
    });
  });
});
