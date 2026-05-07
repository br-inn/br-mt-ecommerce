import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProveedorEditClient } from "../../_components/proveedor-edit-client";

interface PageProps {
  params: Promise<{ code: string }>;
}

/** Edita un proveedor existente. */
export default async function EditProveedorPage({ params }: PageProps) {
  const { code } = await params;
  const t = await getTranslations("proveedores.editPage");
  const tCommon = await getTranslations("common");

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href={`/proveedores/${encodeURIComponent(code)}`}>
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <ProveedorEditClient code={decodeURIComponent(code)} />
    </div>
  );
}
