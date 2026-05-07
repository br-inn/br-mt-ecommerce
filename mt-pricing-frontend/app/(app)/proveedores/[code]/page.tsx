import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProveedorDetail } from "../_components/proveedor-detail";

interface PageProps {
  params: Promise<{ code: string }>;
}

/** Detalle proveedor con tabs (Datos / Costos / Auditoría). */
export default async function ProveedorDetailPage({ params }: PageProps) {
  const { code } = await params;
  const tCommon = await getTranslations("common");
  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href="/proveedores">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <ProveedorDetail code={decodeURIComponent(code)} />
    </div>
  );
}
