import { test } from "@playwright/test";

/**
 * Diagnóstico de errores en consola — abre /login, captura todos los console
 * messages + network failures, los imprime a stdout y guarda screenshot.
 *
 * Uso (desde container mt-frontend):
 *   pnpm exec playwright test tests/e2e/diagnose-console.spec.ts --reporter=list
 */
test("diagnose console errors on /login", async ({ page }) => {
  const consoleMessages: { type: string; text: string; location?: string }[] =
    [];
  const pageErrors: string[] = [];
  const failedRequests: { url: string; failure: string }[] = [];

  page.on("console", (msg) => {
    consoleMessages.push({
      type: msg.type(),
      text: msg.text(),
      location: msg.location().url,
    });
  });
  page.on("pageerror", (err) => {
    pageErrors.push(err.message + "\n" + (err.stack ?? ""));
  });
  page.on("requestfailed", (req) => {
    failedRequests.push({
      url: req.url(),
      failure: req.failure()?.errorText ?? "unknown",
    });
  });

  await page.goto("http://caddy/login", { waitUntil: "networkidle", timeout: 30000 });

  // Pequeño delay para que React/HMR termine de renderizar y dispare cualquier error async.
  await page.waitForTimeout(3000);

  await page.screenshot({ path: "/tmp/diagnose-login.png", fullPage: true });

  console.log("\n========== CONSOLE MESSAGES ==========");
  for (const m of consoleMessages) {
    console.log(`[${m.type.toUpperCase()}] ${m.text}`);
    if (m.location) console.log(`    @ ${m.location}`);
  }
  console.log("\n========== PAGE ERRORS ==========");
  for (const e of pageErrors) console.log(e + "\n---");
  console.log("\n========== FAILED REQUESTS ==========");
  for (const r of failedRequests) console.log(`${r.url} → ${r.failure}`);
  console.log("\n========== SUMMARY ==========");
  console.log(`Total console messages: ${consoleMessages.length}`);
  console.log(
    `Errors: ${consoleMessages.filter((m) => m.type === "error").length}`,
  );
  console.log(
    `Warnings: ${consoleMessages.filter((m) => m.type === "warning").length}`,
  );
  console.log(`Page errors (uncaught): ${pageErrors.length}`);
  console.log(`Failed network requests: ${failedRequests.length}`);
});
