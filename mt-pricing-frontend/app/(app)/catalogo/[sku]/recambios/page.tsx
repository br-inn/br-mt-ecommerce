import { ProductCompatibilityTabClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

/**
 * Tab "Recambios / Compatibilidad" del SKU detail (Fase 5).
 *
 * Server Component fino. UI completa (lista + form con owner_type + DN range)
 * vive en `_client.tsx`.
 */
export default async function ProductCompatibilityPage({ params }: PageProps) {
  const { sku } = await params;
  return <ProductCompatibilityTabClient sku={decodeURIComponent(sku)} />;
}
