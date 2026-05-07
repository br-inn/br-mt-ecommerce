import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProveedorFormClient } from "../_components/proveedor-form-client";

/** Alta de proveedor — wrapper SC + Client form. */
export default async function NewProveedorPage() {
  const t = await getTranslations("proveedores.newPage");
  const tCommon = await getTranslations("common");
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href="/proveedores">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <ProveedorFormClient />
    </div>
  );
}
