import { DimensionTable } from "@/components/domain/dimension-table";
import { PressureTemperatureChart } from "@/components/domain/pressure-temperature-chart";
import { ProductBoreDimensions } from "./_components/product-bore-dimensions";
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
      <section aria-label="Atributos técnicos" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Atributos técnicos
        </h2>
        <ProductSpecsCardEAVConnected sku={sku} />
      </section>
      <section aria-label="Dimensiones por norma" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Dimensiones por norma
        </h2>
        <ProductBoreDimensions sku={sku} />
      </section>
      <section aria-label="Tabla dimensional" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Tabla dimensional
        </h2>
        <DimensionTable sku={sku} />
      </section>
      <section aria-label="Curva presión–temperatura" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Curva presión–temperatura
        </h2>
        <PressureTemperatureChart sku={sku} />
      </section>
    </div>
  );
}
