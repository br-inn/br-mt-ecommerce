import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProductDetail } from "../_components/product-detail";

interface PageProps {
  params: Promise<{ sku: string }>;
}

/**
 * Pantalla 3 — Detalle de producto + tab "Ficha técnica" (US-1A-02-03-S1).
 *
 * Server component que pinta back link y delega a `ProductDetail` (cliente)
 * para fetch + render de tabs y ficha técnica.
 */
export default async function ProductDetailPage({ params }: PageProps) {
  const { sku } = await params;
  const tCommon = await getTranslations("common");

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href="/products">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <ProductDetail sku={sku} />
    </div>
  );
}
