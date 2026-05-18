import { DimensionTable } from "@/components/domain/dimension-table";
import { PressureTemperatureChart } from "@/components/domain/pressure-temperature-chart";
import { ProductBoreDimensions } from "./_components/product-bore-dimensions";
import { ProductCertificates } from "./_components/product-certificates";
import { ProductFlowData } from "./_components/product-flow-data";
import { ProductMaterials } from "./_components/product-materials";
import { ProductSpecs } from "./_components/product-specs";
import { ProductSpecsCardEAVConnected } from "./_components/product-specs-eav-connected";

export default async function ProductSpecsPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return (
    <div className="flex flex-col gap-6">
      <ProductSpecs sku={sku} />
      <ProductSpecsCardEAVConnected sku={sku} />
      <ProductMaterials sku={sku} />
      <ProductBoreDimensions sku={sku} />
      <DimensionTable sku={sku} />
      <PressureTemperatureChart sku={sku} />
      <ProductFlowData sku={sku} />
      <ProductCertificates sku={sku} />
    </div>
  );
}
