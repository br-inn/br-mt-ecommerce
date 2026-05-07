import {
  defineConfig,
  devices,
  type PlaywrightTestConfig,
} from "@playwright/test";

// Bajo `exactOptionalPropertyTypes: true`, asignar `undefined` a propiedades
// opcionales rompe los overloads de defineConfig. Construimos el objeto con
// solo las claves presentes y pasamos `webServer` únicamente en CI.
const baseConfig: PlaywrightTestConfig = {
  testDir: "./",
  fullyParallel: true,
  forbidOnly: !!process.env["CI"],
  retries: process.env["CI"] ? 2 : 0,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    // Default = Caddy single-entry-point (`localhost:8080`). Override via
    // `E2E_BASE_URL` para apuntar a Next dev directo (`http://localhost:3000`).
    baseURL: process.env["E2E_BASE_URL"] ?? "http://localhost:8080",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Timeouts generosos — Next.js dev primer render es lento.
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  // Aserciones esperadas
  expect: {
    timeout: 10_000,
  },
  // Test timeout global
  timeout: 60_000,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
};

if (process.env["CI"]) {
  baseConfig.workers = 1;
  baseConfig.webServer = {
    command: "pnpm start",
    url: "http://localhost:3000",
    reuseExistingServer: false,
    timeout: 120_000,
  };
}

export default defineConfig(baseConfig);
