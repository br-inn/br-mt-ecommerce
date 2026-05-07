export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

/** Nombre de la cookie que persiste la preferencia de idioma (US-1A-01-06-S1). */
export const LOCALE_COOKIE = "mt-locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "es" || value === "en";
}

/** Resuelve un locale válido aplicando precedencia env → default. */
export function resolveEnvLocale(envValue: string | null | undefined): Locale {
  return isLocale(envValue) ? envValue : defaultLocale;
}
