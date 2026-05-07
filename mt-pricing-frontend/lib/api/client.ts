import createClient from "openapi-fetch";
import env from "@/lib/env";
import type { paths } from "@/lib/api/types";

/**
 * Typed backend client.
 *
 * Agente G enriches `paths` via `pnpm openapi:gen` and adds endpoint helpers
 * under `lib/api/endpoints/`.
 */
export const apiClient = createClient<paths>({
  baseUrl: env.NEXT_PUBLIC_BACKEND_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export type ApiClient = typeof apiClient;
