import { AmazonContenidoConnected } from "../_components/amazon-contenido-connected";

export default async function AmazonListingContenidoPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <AmazonContenidoConnected sku={sku} />;
}
