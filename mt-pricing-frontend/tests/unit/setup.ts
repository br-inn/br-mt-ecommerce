import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock obligatorio: lib/env.ts valida vars con zod en import-time. Sin estos
// valores, cualquier módulo que cargue lib/env.ts (vía lib/api/endpoints/*)
// lanza "Invalid environment variables" durante la fase de collect de Vitest.
// Se setean antes de cualquier import dinámico/estático en los tests.
process.env["NEXT_PUBLIC_SUPABASE_URL"] ??= "https://test.supabase.co";
process.env["NEXT_PUBLIC_SUPABASE_ANON_KEY"] ??= "test-anon-key";
process.env["NEXT_PUBLIC_BACKEND_URL"] ??= "http://localhost:8000";
process.env["NEXT_PUBLIC_DEFAULT_LOCALE"] ??= "es";

afterEach(() => {
  cleanup();
});
