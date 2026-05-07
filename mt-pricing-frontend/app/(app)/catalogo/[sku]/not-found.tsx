import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Button } from "@/components/ui/button";

export default async function ProductNotFound() {
  const t = await getTranslations("catalog");
  const tErrors = await getTranslations("errors");
  const tCommon = await getTranslations("common");
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <h2 className="text-xl font-semibold">{tErrors("notFoundTitle")}</h2>
      <p className="max-w-sm text-sm text-muted-foreground">{t("errors.notFound")}</p>
      <Button asChild>
        <Link href="/catalogo">{tCommon("back")}</Link>
      </Button>
    </div>
  );
}
