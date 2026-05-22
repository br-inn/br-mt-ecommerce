"use client";

import { useProduct } from "@/lib/hooks/products/use-product";
import { useProductTranslations } from "@/lib/hooks/products/use-translations";
import { TranslationsTab } from "../_components/translations-tab";

interface Props {
  sku: string;
}

/**
 * Fetches translations for the product and renders the coverage + AI-completion
 * overview panel above the detailed workflow editor.
 */
export function TranslationsOverviewPanel({ sku }: Props) {
  const { data: product } = useProduct(sku);
  const { data: translations } = useProductTranslations(product?.id);

  const rows = (translations ?? []).map((t) => ({
    lang: t.language,
    name: t.name,
    status: t.status,
  }));

  return (
    <div className="px-6 pt-4 pb-2">
      <TranslationsTab sku={sku} translations={rows} />
    </div>
  );
}
