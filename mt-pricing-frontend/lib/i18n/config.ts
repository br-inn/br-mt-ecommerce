// "ar" is intentionally excluded — Arabic is a product-content language only,
// not a system UI locale. Product translations to Arabic are managed via
// the product_translations table and shown within the ES/EN interface.
export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

/** Locales that need RTL document direction. */
export const RTL_LOCALES: readonly Locale[] = [] as const;

/** Nombre de la cookie que persiste la preferencia de idioma (US-1A-01-06-S1). */
export const LOCALE_COOKIE = "mt-locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "es" || value === "en" || value === "ar";
}

/** Resuelve un locale válido aplicando precedencia env → default. */
export function resolveEnvLocale(envValue: string | null | undefined): Locale {
  return isLocale(envValue) ? envValue : defaultLocale;
}

/** True si el locale requiere `dir="rtl"` en el `<html>` root. */
export function isRtlLocale(locale: Locale): boolean {
  return RTL_LOCALES.includes(locale);
}

/** Devuelve `"rtl"` o `"ltr"` para usar en `<html dir>`. */
export function localeDirection(locale: Locale): "rtl" | "ltr" {
  return isRtlLocale(locale) ? "rtl" : "ltr";
}
