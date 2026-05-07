import { createBrowserClient } from "@supabase/ssr";

import env from "@/lib/env";

/**
 * Cliente Supabase para el browser. Usa publishable_key (o anon_key fallback).
 * Llamar dentro de Client Components / hooks.
 */
export function createClient() {
  return createBrowserClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_KEY,
  );
}

/** Alias legacy para compatibilidad con código del Wave 1/2. */
export const createSupabaseBrowserClient = createClient;
