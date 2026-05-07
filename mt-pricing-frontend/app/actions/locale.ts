"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { LOCALE_COOKIE, isLocale, type Locale } from "@/lib/i18n/config";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365; // 1 año

/**
 * Server Action: persiste el locale del usuario en una cookie HTTPOnly=false
 * (necesita ser legible si en el futuro algo client la necesita) y revalida
 * el árbol para que el RSC sirva los nuevos messages (US-1A-01-06-S1).
 */
export async function setLocale(next: Locale): Promise<{ ok: boolean; locale: Locale }> {
  if (!isLocale(next)) {
    return { ok: false, locale: next };
  }

  const cookieStore = await cookies();
  cookieStore.set(LOCALE_COOKIE, next, {
    maxAge: COOKIE_MAX_AGE_SECONDS,
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });

  // Revalida el layout para que el server vuelva a renderizar con el nuevo idioma.
  revalidatePath("/", "layout");

  return { ok: true, locale: next };
}
