import { PriceDetailClient } from "./_client";

interface PageProps {
  params: Promise<{ id: string }>;
}

/**
 * `/precios/[id]` — detalle de propuesta (US-1B-01-06 S4).
 *
 * Server Component fino que resuelve `params` y delega a la island cliente.
 * Toda la lógica de fetch + acciones vive en `_client.tsx`.
 */
export default async function PriceDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <PriceDetailClient id={decodeURIComponent(id)} />;
}
