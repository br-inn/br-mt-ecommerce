import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";

import env from "@/lib/env";

/**
 * Cliente Supabase para Server Components / Server Actions / Route Handlers.
 * Lee y escribe cookies para mantener la sesión.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_KEY,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(
          cookiesToSet: {
            name: string;
            value: string;
            options: CookieOptions;
          }[],
        ) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // Server Component context — middleware refrescará la cookie.
          }
        },
      },
    },
  );
}

/** Alias legacy para compatibilidad con código del Wave 1/2. */
export const createSupabaseServerClient = createClient;
