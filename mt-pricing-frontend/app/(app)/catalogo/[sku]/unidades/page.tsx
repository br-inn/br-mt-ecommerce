import { UnidadesClient } from "./_client";

export default async function UnidadesPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <UnidadesClient sku={sku} />;
}
