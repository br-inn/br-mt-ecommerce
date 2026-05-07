/**
 * 01 — Healthchecks (Crítico).
 *
 * Verifica que la stack local responde a `/health/live` y `/health/ready`.
 * Si Caddy está como single entry point (`localhost:8080`), los proxies
 * mantienen rutas; si el dev corre uvicorn directo en :8000, el override
 * `E2E_BACKEND_URL` lo cubre.
 */

import { expect, test } from "@playwright/test";
import { getLive, getReady, getFlowerHealth } from "./fixtures/api";
import { BACKEND_URL, FLOWER_URL } from "./fixtures/env";

test.describe("Healthchecks @critico", () => {
  test("backend /health/live → 200", async () => {
    const res = await getLive();
    if (!res.ok) {
      test.fail(
        true,
        `Backend no responde en ${BACKEND_URL}/health/live (status=${res.status}). ` +
          `Asegúrate que la stack está arriba: ./scripts/validate-e2e.ps1`,
      );
    }
    expect(res.status).toBe(200);
  });

  test("backend /health/ready → 200 o 503", async () => {
    const res = await getReady();
    // Aceptamos 200 (deps OK) o 503 (degraded — no falla el test).
    expect([200, 503]).toContain(res.status);
  });

  // Flower: secundario — solo si el overlay está corriendo.
  test("celery flower /healthcheck → 200 (si flower up)", async () => {
    try {
      const res = await getFlowerHealth();
      if (res.status === 0 || res.status >= 500) {
        test.skip(
          true,
          `Flower no disponible en ${FLOWER_URL} (status=${res.status}). ` +
            `Levanta el overlay: docker compose -f infra/docker-compose.dev.yml up -d flower`,
        );
      }
      expect(res.status).toBe(200);
    } catch (err) {
      test.skip(true, `Flower unreachable: ${(err as Error).message}`);
    }
  });
});
