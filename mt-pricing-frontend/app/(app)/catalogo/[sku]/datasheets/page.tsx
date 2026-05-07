import { DatasheetsTabClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

/**
 * Tab "Documentos" del SKU detail (US-1A-06-04 frontend Sprint 4).
 *
 * Server Component fino. UI completa (lista + uploader + preview) en
 * `_client.tsx`.
 */
export default async function ProductDatasheetsPage({ params }: PageProps) {
  const { sku } = await params;
  return <DatasheetsTabClient sku={decodeURIComponent(sku)} />;
}
