import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProductHeader } from "./_components/product-header";
import { ProductTabs } from "./_components/product-tabs";

interface LayoutProps {
  children: ReactNode;
  params: Promise<{ sku: string }>;
}

export default async function ProductDetailLayout({ children, params }: LayoutProps) {
  const { sku } = await params;
  const tCommon = await getTranslations("common");

  return (
    <div className="mx-auto max-w-screen-xl space-y-6 px-6 py-6">
      <Button asChild variant="ghost" size="sm" className="-ml-1 w-fit">
        <Link href="/catalogo">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>

      <ProductHeader sku={sku} />
      <ProductTabs sku={sku} />
      <div>{children}</div>
    </div>
  );
}
