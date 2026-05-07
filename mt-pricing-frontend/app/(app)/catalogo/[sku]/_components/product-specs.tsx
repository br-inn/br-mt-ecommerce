"use client";

import { useTranslations } from "next-intl";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProduct } from "@/lib/hooks/products/use-product";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground sm:w-44">{label}</dt>
      <dd className="text-sm font-medium">{value ?? "—"}</dd>
    </div>
  );
}

export function ProductSpecs({ sku }: { sku: string }) {
  const t = useTranslations("catalog");
  const tFields = useTranslations("catalog.product.fields");
  const { data, isLoading, isError } = useProduct(sku);

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-64 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !data) {
    return <p className="text-sm text-destructive">{t("errors.notFound")}</p>;
  }

  const dim = data.dimensions;
  const dimText = dim
    ? `${dim.length ?? "—"} × ${dim.width ?? "—"} × ${dim.height ?? "—"} ${dim.unit ?? ""}`
    : "—";

  const pkg = data.packaging;
  const intra = data.intrastat;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{t("product.specs.title")}</CardTitle>
          <CardDescription>{t("product.specs.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("dn")} value={data.dn} />
            <Row label={tFields("pn")} value={data.pn} />
            <Row label={tFields("material")} value={data.material} />
            <Row label={tFields("type")} value={data.type} />
            <Row label={tFields("connection")} value={data.connection} />
            <Row label={tFields("weight_kg")} value={data.weight_kg} />
            <Row label={tFields("dimensions")} value={dimText} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("product.packaging.title")}</CardTitle>
          <CardDescription>{t("product.packaging.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("qty_x_box")} value={pkg?.qty_x_box} />
            <Row label={tFields("ean_unit")} value={pkg?.ean_unit} />
            <Row label={tFields("ean_box")} value={pkg?.ean_box} />
            <Row label={tFields("moq")} value={pkg?.moq} />
            <Row label={tFields("hs_code")} value={intra?.hs_code} />
            <Row label={tFields("origin_country")} value={intra?.origin_country} />
            <Row label={tFields("net_weight_kg")} value={intra?.net_weight_kg} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
