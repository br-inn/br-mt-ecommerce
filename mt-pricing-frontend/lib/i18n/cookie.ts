import { cookies, headers } from "next/headers";
import {
  LOCALE_COOKIE,
  defaultLocale,
  isLocale,
  type Locale,
} from "@/lib/i18n/config";

/**
 * Resuelve el locale activo en server side (US-1A-01-06-S1).
 *
 * Precedencia:
 *  1. Cookie `mt-locale` (preferencia explícita del usuario).
 *  2. Cabecera `Accept-Language` del browser.
 *  3. Env `NEXT_PUBLIC_DEFAULT_LOCALE`.
 *  4. `defaultLocale` ("es").
 */
export async function resolveLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const fromCookie = cookieStore.get(LOCALE_COOKIE)?.value;
  if (isLocale(fromCookie)) return fromCookie;

  try {
    const hdrs = await headers();
    const accept = hdrs.get("accept-language");
    if (accept) {
      const primary = accept.split(",")[0]?.split(";")[0]?.trim().toLowerCase() ?? "";
      if (primary.startsWith("es")) return "es";
      if (primary.startsWith("en")) return "en";
    }
  } catch {
    // headers() lanza fuera de un server context — fallback a env/default.
  }

  const envValue = process.env["NEXT_PUBLIC_DEFAULT_LOCALE"];
  if (isLocale(envValue)) return envValue;

  return defaultLocale;
}
