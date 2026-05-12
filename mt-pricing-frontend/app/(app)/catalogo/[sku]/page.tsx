import { DimensionTable } from "@/components/domain/dimension-table";
import { PressureTemperatureChart } from "@/components/domain/pressure-temperature-chart";
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
      <section
        aria-label="Stage 2 — EAV attributes"
        className="flex flex-col gap-2"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Stage 2 — EAV
        </h2>
        {/*
          Fase B — `family_id` viene del backend `ProductResponse`.
          Si el producto es legacy (sin `family_id`) el card hace render
          de un placeholder explicativo.
        */}
        <ProductSpecsCardEAVConnected sku={sku} />
      </section>
      <section
        aria-label="Fase 3 — Tabla dimensional"
        className="flex flex-col gap-2"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Tabla Dimensional
        </h2>
        <DimensionTable sku={sku} />
      </section>
      <section
        aria-label="Fase 3 — Curva Presion-Temperatura"
        className="flex flex-col gap-2"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Curva Presion-Temperatura
        </h2>
        <PressureTemperatureChart sku={sku} />
      </section>
    </div>
  );
}
