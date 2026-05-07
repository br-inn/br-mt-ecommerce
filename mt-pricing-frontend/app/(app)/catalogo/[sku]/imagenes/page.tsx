import { getTranslations } from "next-intl/server";
import { ImagesTab } from "./_client";

export default async function ProductImagesPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  const t = await getTranslations("catalog.images");
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <ImagesTab sku={sku} />
    </div>
  );
}
