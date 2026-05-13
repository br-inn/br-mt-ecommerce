import { MercadosClient } from "./_client";

export default async function MercadosPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <MercadosClient sku={sku} />;
}
