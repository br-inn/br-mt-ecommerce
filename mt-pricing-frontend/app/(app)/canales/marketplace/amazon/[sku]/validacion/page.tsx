import { AmazonValidacionConnected } from "../_components/amazon-validacion-connected";

export default async function AmazonListingValidacionPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <AmazonValidacionConnected sku={sku} />;
}
