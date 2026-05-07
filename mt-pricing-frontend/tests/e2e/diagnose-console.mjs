import { chromium } from "playwright";

/**
 * Diagnóstico console — abre /login en chromium headless y captura todos los
 * eventos de consola, pageerror y request failures.
 *
 * Uso (desde container ad-hoc):
 *   node /diagnose.mjs
 */
const TARGET = process.env.TARGET_URL || "http://caddy/login";

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
const page = await ctx.newPage();

const consoleMessages = [];
const pageErrors = [];
const failedRequests = [];

page.on("console", (msg) => {
  consoleMessages.push({
    type: msg.type(),
    text: msg.text(),
    url: msg.location()?.url,
  });
});
page.on("pageerror", (err) => pageErrors.push(`${err.message}\n${err.stack ?? ""}`));
page.on("requestfailed", (req) =>
  failedRequests.push({ url: req.url(), failure: req.failure()?.errorText ?? "?" }),
);

console.log(`[i] Navegando a ${TARGET}`);
try {
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
} catch (e) {
  console.log(`[!] Goto falló: ${e.message}`);
}
await page.waitForTimeout(3000);

console.log("\n========== CONSOLE MESSAGES ==========");
for (const m of consoleMessages) {
  console.log(`[${m.type.toUpperCase()}] ${m.text}`);
  if (m.url) console.log(`    @ ${m.url}`);
}
console.log("\n========== PAGE ERRORS (uncaught) ==========");
if (pageErrors.length === 0) console.log("(none)");
for (const e of pageErrors) console.log(e + "\n---");
console.log("\n========== FAILED NETWORK REQUESTS ==========");
if (failedRequests.length === 0) console.log("(none)");
for (const r of failedRequests) console.log(`${r.url} → ${r.failure}`);

console.log("\n========== SUMMARY ==========");
const errors = consoleMessages.filter((m) => m.type === "error").length;
const warnings = consoleMessages.filter((m) => m.type === "warning").length;
console.log(`Total console messages: ${consoleMessages.length}`);
console.log(`  errors:    ${errors}`);
console.log(`  warnings:  ${warnings}`);
console.log(`Uncaught page errors:   ${pageErrors.length}`);
console.log(`Failed network reqs:    ${failedRequests.length}`);

await browser.close();
