import { MtTraduccionesClient } from "./_mt-client";

export default async function ProductTranslationsPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <MtTraduccionesClient sku={sku} />;
}
