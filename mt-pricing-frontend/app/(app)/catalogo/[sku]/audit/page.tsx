import { AuditTabClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

/**
 * Tab "Auditoría" del SKU detail (US-1A-07-03-FE Sprint 4).
 *
 * Server Component fino: resuelve `params` y delega a la island cliente.
 * La UI completa (tabla + timeline + filtros) vive en `_client.tsx`.
 */
export default async function ProductAuditPage({ params }: PageProps) {
  const { sku } = await params;
  return <AuditTabClient sku={decodeURIComponent(sku)} />;
}
