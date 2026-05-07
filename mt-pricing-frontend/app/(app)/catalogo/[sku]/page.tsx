import { ProductSpecs } from "./_components/product-specs";

export default async function ProductSpecsPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <ProductSpecs sku={sku} />;
}
