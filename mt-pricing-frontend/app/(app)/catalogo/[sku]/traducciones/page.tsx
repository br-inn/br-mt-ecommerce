import { MtTraduccionesClient } from "./_mt-client";
import { TranslationsOverviewPanel } from "./_translations-overview";

export default async function ProductTranslationsPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return (
    <>
      <TranslationsOverviewPanel sku={sku} />
      <MtTraduccionesClient sku={sku} />
    </>
  );
}
