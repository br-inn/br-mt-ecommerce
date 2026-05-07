import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { ProductWizard } from "../_components/product-wizard";

export default async function NewProductPage() {
  const t = await getTranslations("catalog.create");
  const tCommon = await getTranslations("common");
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 w-fit">
        <Link href="/catalogo">
          <ChevronLeft className="h-4 w-4" /> {tCommon("back")}
        </Link>
      </Button>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <ProductWizard />
    </div>
  );
}
