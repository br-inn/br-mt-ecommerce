import { AmazonDatosConnected } from "./_components/amazon-datos-connected";

export default async function AmazonListingDatosPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <AmazonDatosConnected sku={sku} />;
}
