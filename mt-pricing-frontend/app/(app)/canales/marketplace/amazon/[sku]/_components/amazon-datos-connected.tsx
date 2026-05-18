"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Info } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MT } from "@/components/mt/tokens";
import { useProduct } from "@/lib/hooks/products/use-product";

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground sm:w-44">{label}</dt>
      <dd className={`text-sm font-medium ${mono ? "font-mono" : ""}`}>{value ?? "—"}</dd>
    </div>
  );
}

interface Props {
  sku: string;
}

export function AmazonDatosConnected({ sku }: Props) {
  const router = useRouter();
  const { data: product, isLoading, isError } = useProduct(sku);

  const handleEditInCatalog = useCallback(() => {
    try {
      sessionStorage.setItem("mt-catalog-return", `/canales/marketplace/amazon/${sku}`);
    } catch {
      // ignore — sessionStorage unavailable
    }
    router.push(`/catalogo/${sku}`);
  }, [router, sku]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-40" />
            </CardHeader>
            <CardContent className="space-y-3">
              {[1, 2, 3].map((j) => (
                <Skeleton key={j} className="h-4 w-full" />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        No se pudo cargar el producto.
      </div>
    );
  }

  const intrastat = product.intrastat ?? {};
  const tempMin = product.temp_min_c ?? null;
  const tempMax = product.temp_max_c ?? null;
  const tempRange =
    tempMin !== null && tempMax !== null
      ? `${tempMin}°C — ${tempMax}°C`
      : tempMin !== null
        ? `≥ ${tempMin}°C`
        : tempMax !== null
          ? `≤ ${tempMax}°C`
          : null;

  return (
    <div className="flex flex-col gap-6">
      {/* ── Aviso lectura + acceso a edición ── */}
      <div
        className="flex items-start justify-between gap-4 rounded-md border px-4 py-3"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <div className="flex items-start gap-2.5 text-[12.5px]" style={{ color: MT.ink3 }}>
          <Info className="mt-px size-4 shrink-0" style={{ color: MT.brand }} />
          <p>
            Estos datos provienen de la ficha del producto y son de{" "}
            <strong className="font-semibold" style={{ color: MT.ink2 }}>solo lectura</strong> en esta vista.
            Para modificarlos, accede a la ficha del artículo.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleEditInCatalog}
          className="shrink-0 gap-1.5 text-[12.5px]"
        >
          Editar ficha
          <ArrowUpRight className="size-3.5" />
        </Button>
      </div>

      {/* ── Identificación ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Identificación</CardTitle>
          <CardDescription>Campos de identidad enviados al feed de Amazon</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label="SKU" value={product.sku} mono />
            <Row label="GTIN / EAN" value={product.gtin} mono />
            <Row label="DN" value={product.dn} />
            <Row label="PN" value={product.pn} />
            <Row label="Familia" value={product.family} />
            <Row label="Material" value={product.material} />
            <Row label="Conexión" value={product.connection} />
          </dl>
        </CardContent>
      </Card>

      {/* ── Datos físicos ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Datos físicos</CardTitle>
          <CardDescription>Peso, dimensiones y condiciones de operación</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label="Peso" value={product.weight_kg ? `${product.weight_kg} kg` : null} />
            <Row
              label="Presión máx."
              value={product.pressure_max_bar ? `${product.pressure_max_bar} bar` : null}
            />
            <Row label="Temperatura" value={tempRange} />
            {product.dimensions ? (
              <Row
                label="Dimensiones (L×A×H)"
                value={
                  [product.dimensions.length, product.dimensions.width, product.dimensions.height]
                    .filter((v) => v != null)
                    .join(" × ") + (product.dimensions.unit ? ` ${product.dimensions.unit}` : "")
                }
              />
            ) : null}
          </dl>
        </CardContent>
      </Card>

      {/* ── Comercio exterior ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comercio exterior</CardTitle>
          <CardDescription>Información aduanera para exportación UAE</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label="País de origen" value={intrastat.origin_country} />
            <Row label="Código HS" value={intrastat.hs_code} mono />
            <Row label="Peso neto" value={intrastat.net_weight_kg ? `${intrastat.net_weight_kg} kg` : null} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
