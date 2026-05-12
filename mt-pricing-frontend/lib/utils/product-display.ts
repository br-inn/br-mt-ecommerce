/**
 * Resolución de display-strings para producto post-Fase B.
 *
 * Backend dropeó `products.name_en`, `products.description_en`,
 * `products.marketing_copy_en`. Las traducciones EN viven ahora en
 * `product_translations(lang='en')`. El backend expone un objeto
 * `translations` opcional en `ProductResponse` que puede tener forma:
 *
 *   - Record por idioma: `{ en: { name, description, marketing_copy }, es: { ... } }`
 *   - O array: `[{ lang: 'en', name, description, marketing_copy }, ...]`
 *
 * Estos helpers cubren ambos formatos sin que cada componente tenga que
 * preocuparse de la forma exacta.
 */

interface TranslationRecord {
  name?: string | null;
  description?: string | null;
  marketing_copy?: string | null;
}

interface TranslationArrayItem extends TranslationRecord {
  lang?: string | null;
  language?: string | null;
}

interface MaybeTranslated {
  translations?: unknown;
}

function pickTranslation(
  p: MaybeTranslated,
  lang: string,
): TranslationRecord | undefined {
  const t = p.translations;
  if (!t) return undefined;
  if (Array.isArray(t)) {
    const arr = t as TranslationArrayItem[];
    return arr.find((it) => (it.lang ?? it.language) === lang);
  }
  if (typeof t === "object") {
    const rec = t as Record<string, TranslationRecord | undefined | null>;
    return rec[lang] ?? undefined;
  }
  return undefined;
}

const FALLBACK_NAME = "(sin nombre)";

export function getProductName(p: MaybeTranslated): string {
  const tr = pickTranslation(p, "en");
  return tr?.name ?? FALLBACK_NAME;
}

export function getProductDescription(
  p: MaybeTranslated,
): string | null {
  const tr = pickTranslation(p, "en");
  return tr?.description ?? null;
}

export function getProductMarketingCopy(
  p: MaybeTranslated,
): string | null {
  const tr = pickTranslation(p, "en");
  return tr?.marketing_copy ?? null;
}
