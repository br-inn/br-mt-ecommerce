/**
 * 22 — Scraper wizard AI-powered creation @critico
 *
 * Flow: open dialog → enter URL (local fixture server) → wait for Claude analysis
 * → verify proposed fields → click "Crear scraper" → assert toast + source in list.
 *
 * Requires:
 *   - App running at PLAYWRIGHT_BASE_URL (default http://localhost:3000)
 *   - Backend at NEXT_PUBLIC_BACKEND_URL with ANTHROPIC_API_KEY set
 *   - SCRAPER_ALLOW_LOOPBACK=true in backend container env
 */
import * as fs from "node:fs";
import * as http from "node:http";
import * as path from "node:path";

import { expect, test } from "@playwright/test";

import { loginAsGerente } from "./helpers/auth-as-role";

// ── Local HTML fixture server ──────────────────────────────────────────────
let fixtureServer: http.Server;
let fixtureBaseUrl: string;

const FIXTURES_DIR = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "mt-pricing-backend",
  "tests",
  "fixtures",
  "html",
);

test.beforeAll(async () => {
  await new Promise<void>((resolve) => {
    fixtureServer = http.createServer((req, res) => {
      const filePath = path.join(
        FIXTURES_DIR,
        (req.url ?? "/").replace(/^\//, "") || "index.html",
      );
      if (!fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(fs.readFileSync(filePath));
    });
    fixtureServer.listen(0, "0.0.0.0", () => {
      const addr = fixtureServer.address() as { port: number };
      // Use host.docker.internal if backend is in Docker, else 127.0.0.1
      const host = process.env.FIXTURE_SERVER_HOST ?? "127.0.0.1";
      fixtureBaseUrl = `http://${host}:${addr.port}`;
      resolve();
    });
  });
});

test.afterAll(() => {
  fixtureServer.close();
});

// ── Tests ──────────────────────────────────────────────────────────────────
test.describe("Scraper wizard @critico", () => {
  test("creates a scraper via AI wizard and appears in list", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    // Open dialog
    await page.getByRole("button", { name: /new source|nueva? source/i }).click();

    // Wizard Step 1 — URL form
    await expect(page.getByText(/crear scraper con ai/i)).toBeVisible({ timeout: 5_000 });
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/generic_serp.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    // Wait for analyzing state
    await expect(page.getByText(/claude está analizando/i)).toBeVisible({ timeout: 5_000 });

    // Wait for review state — Claude must respond (up to 60s)
    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Verify at least one proposed field is visible
    await expect(page.getByText("title").first()).toBeVisible({ timeout: 5_000 });

    // Click "Crear scraper"
    await page.getByRole("button", { name: /crear scraper/i }).click();

    // Wait for success toast
    await expect(page.getByText(/scraper creado/i)).toBeVisible({ timeout: 30_000 });

    // Verify source appears in list
    await expect(page.getByText("127.0.0.1").first()).toBeVisible({ timeout: 5_000 });
  });

  test("shows warning banner for headless-detected sites", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    await page.getByRole("button", { name: /new source|nueva? source/i }).click();
    await expect(page.getByText(/crear scraper con ai/i)).toBeVisible({ timeout: 5_000 });
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/js_heavy.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    // Wait for review
    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Should show headless warning banner
    await expect(page.getByText(/navegador headless/i)).toBeVisible({ timeout: 5_000 });
  });

  test("can add a field manually", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    await page.getByRole("button", { name: /new source|nueva? source/i }).click();
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/generic_serp.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Click "Agregar campo"
    await page.getByRole("button", { name: /agregar campo/i }).click();

    // Switch to Manual mode
    await page.getByRole("button", { name: /^manual$/i }).click();

    // Fill in the new field
    await page.getByLabel(/^campo$/i).fill("custom_field");
    await page.getByLabel(/selector css/i).fill("span.custom");
    await page.getByRole("button", { name: /^agregar$/i }).click();

    // Verify the field appears in the list
    await expect(page.getByText("custom_field").first()).toBeVisible({ timeout: 3_000 });
  });
});
