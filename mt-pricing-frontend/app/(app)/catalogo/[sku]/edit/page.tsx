import { getTranslations } from "next-intl/server";
import { EditClient } from "./_client";

export default async function ProductEditPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  const t = await getTranslations("catalog.edit");
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <EditClient sku={sku} />
    </div>
  );
}
