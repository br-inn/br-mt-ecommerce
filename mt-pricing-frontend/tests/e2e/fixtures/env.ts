/**
 * Centralised env resolution for E2E tests.
 *
 * Strategy: por defecto la stack se sirve por Caddy en `localhost:8080` (single
 * entry point), donde `/api/*` → backend y `/` → Next.js. Permitimos override
 * via `E2E_BASE_URL` y `E2E_BACKEND_URL` para correr contra dev directo
 * (`pnpm dev` en :3000 + uvicorn en :8000) cuando el desarrollador prefiere.
 *
 * Fuentes:
 * - `E2E_BASE_URL`: URL del frontend (ej. http://localhost:8080 o :3000)
 * - `E2E_BACKEND_URL`: URL del backend; si no se define, asume `BASE_URL`
 *   (Caddy hace proxy de /api y /health al backend)
 * - `E2E_USE_REAL_SUPABASE`: "1" → no aplicar mocks de Supabase auth
 * - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`: para crear sesión via admin
 */

const trimSlash = (s: string): string => s.replace(/\/+$/u, "");

export const BASE_URL: string = trimSlash(
  process.env["E2E_BASE_URL"] ?? "http://localhost:8080",
);

export const BACKEND_URL: string = trimSlash(
  process.env["E2E_BACKEND_URL"] ?? BASE_URL,
);

export const FLOWER_URL: string = trimSlash(
  process.env["E2E_FLOWER_URL"] ?? "http://localhost:5555",
);

export const USE_REAL_SUPABASE: boolean =
  process.env["E2E_USE_REAL_SUPABASE"] === "1" ||
  process.env["E2E_USE_REAL_SUPABASE"]?.toLowerCase() === "true";

export const SUPABASE_URL: string | undefined = process.env["SUPABASE_URL"];

export const SUPABASE_SERVICE_ROLE_KEY: string | undefined =
  process.env["SUPABASE_SERVICE_ROLE_KEY"];

/**
 * Email del usuario de prueba (override-able). El password se asume preset por
 * `seed_demo.py` durante el bootstrap del orquestador.
 */
export const E2E_USER_EMAIL: string =
  process.env["E2E_USER_EMAIL"] ?? "e2e@mt.ae";

export const E2E_USER_PASSWORD: string =
  process.env["E2E_USER_PASSWORD"] ?? "Test1234!Test1234!";
