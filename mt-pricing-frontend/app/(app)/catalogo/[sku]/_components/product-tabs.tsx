"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils/cn";

interface Props {
  sku: string;
}

/**
 * Tabs URL-driven (Link). El segmento de URL determina la activa, y
 * se mantiene navegable + bookmarkable. Renderizadas con role=tablist
 * para A11y aunque cada item sea un Link.
 */
export function ProductTabs({ sku }: Props) {
  const t = useTranslations("catalog.product.tabs");
  const pathname = usePathname() ?? "";

  const tabs = [
    { href: `/catalogo/${sku}`, label: t("specs"), match: (p: string) => p === `/catalogo/${sku}` },
    {
      href: `/catalogo/${sku}/imagenes`,
      label: t("images"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/imagenes`),
    },
    {
      href: `/catalogo/${sku}/traducciones`,
      label: t("translations"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/traducciones`),
    },
    {
      href: `/catalogo/${sku}/costos`,
      label: t("costs"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/costos`),
    },
    {
      href: `/catalogo/${sku}/datasheets`,
      label: t("datasheets"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/datasheets`),
    },
    {
      href: `/catalogo/${sku}/recambios`,
      label: t("spareParts"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/recambios`),
    },
    {
      href: `/catalogo/${sku}/audit`,
      label: t("audit"),
      match: (p: string) => p.startsWith(`/catalogo/${sku}/audit`),
    },
  ];

  return (
    <nav role="tablist" aria-label={t("specs")} className="border-b">
      <ul className="-mb-px flex flex-wrap gap-1">
        {tabs.map((tab) => {
          const active = tab.match(pathname);
          return (
            <li key={tab.href} role="presentation">
              <Link
                href={tab.href}
                role="tab"
                aria-selected={active}
                className={cn(
                  "inline-flex items-center border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
