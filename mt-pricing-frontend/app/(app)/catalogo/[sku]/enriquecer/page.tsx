import { FichaEnrichClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

export default async function FichaEnrichPage({ params }: PageProps) {
  const { sku } = await params;
  return <FichaEnrichClient sku={decodeURIComponent(sku)} />;
}
