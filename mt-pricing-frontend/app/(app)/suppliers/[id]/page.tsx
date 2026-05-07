import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { SupplierDetail } from "./_components/supplier-detail";

interface PageProps {
  params: Promise<{ id: string }>;
}

/** Detalle / edición de un proveedor (US-1A-03-02 frontend). */
export default async function SupplierDetailPage({ params }: PageProps) {
  const { id } = await params;
  const tCommon = await getTranslations("common");

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href="/suppliers">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <SupplierDetail id={id} />
    </div>
  );
}
