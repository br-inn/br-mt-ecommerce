import { CostsTabClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

/**
 * Tab "Costes" del producto (US-1A-04-04).
 * Server Component fino: resuelve `params` y entrega al cliente la SKU
 * decodificada. Toda la UI vive en `_client.tsx`.
 */
export default async function ProductCostsPage({ params }: PageProps) {
  const { sku } = await params;
  return <CostsTabClient sku={decodeURIComponent(sku)} />;
}
