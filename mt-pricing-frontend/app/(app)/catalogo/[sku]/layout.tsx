import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { ProductHeader } from "./_components/product-header";
import { ProductTabs } from "./_components/product-tabs";
import { ProductBreadcrumb } from "./_components/product-breadcrumb";

interface LayoutProps {
  children: ReactNode;
  params: Promise<{ sku: string }>;
}

export default async function ProductDetailLayout({ children, params }: LayoutProps) {
  const { sku } = await params;
  const tCatalog = await getTranslations("catalog");

  return (
    <div className="mx-auto max-w-screen-xl space-y-6 px-6 py-6">
      {/* Breadcrumb: Catálogo > [SKU] > [Tab activo] */}
      <nav aria-label="Miga de pan" className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link
          href="/catalogo"
          className="hover:text-foreground transition-colors"
        >
          {tCatalog("title")}
        </Link>
        <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        <span className="font-mono text-foreground">{sku}</span>
        <ProductBreadcrumb sku={sku} />
      </nav>

      <ProductHeader sku={sku} />
      <ProductTabs sku={sku} />
      <div>{children}</div>
    </div>
  );
}
