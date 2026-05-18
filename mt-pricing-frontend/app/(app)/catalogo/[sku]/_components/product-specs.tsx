"use client";

import { useTranslations } from "next-intl";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useProduct } from "@/lib/hooks/products/use-product";

function Row({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground sm:w-44">{label}</dt>
      <dd className={`text-sm font-medium ${mono ? "font-mono" : ""}`}>{value ?? "—"}</dd>
    </div>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">{label}</span>
      <Separator className="flex-1" />
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
        <Skeleton className="h-80 w-full rounded-lg" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !data) {
    return <p className="text-sm text-destructive">{t("errors.notFound")}</p>;
  }

  const dim = data.dimensions;
  const dimText = dim
    ? `${dim.length ?? "—"} × ${dim.width ?? "—"} × ${dim.height ?? "—"} ${dim.unit ?? ""}`
    : null;

  const pkg = data.packaging;
  const intra = data.intrastat;

  const tempRange =
    data.temp_min_c != null || data.temp_max_c != null
      ? `${data.temp_min_c ?? "—"} °C — ${data.temp_max_c ?? "—"} °C`
      : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Card 1 — Especificaciones técnicas */}
      <Card>
        <CardHeader>
          <CardTitle>{t("product.specs.title")}</CardTitle>
          <CardDescription>{t("product.specs.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("dn")} value={data.dn ? `DN ${data.dn}` : null} />
            <Row label={tFields("pn")} value={data.pn ? `PN ${data.pn}` : null} />
            <Row
              label={tFields("bore_mm")}
              value={data.bore_mm != null ? `${data.bore_mm} mm` : null}
            />
            <Row label={tFields("dimensional_standard")} value={data.dimensional_standard} />
            <Row label={tFields("temp_range")} value={tempRange} />
            <Row
              label={tFields("pressure_max")}
              value={data.pressure_max_bar != null ? `${data.pressure_max_bar} bar` : null}
            />

            <SectionDivider label={t("product.specs.sectionConstruction")} />

            <Row label={tFields("material")} value={data.material_detail?.name ?? data.material} />
            <Row label={tFields("type")} value={data.type} />
            <Row label={tFields("connection")} value={data.connection} />
            <Row label={tFields("size")} value={data.size} />
            <Row label={tFields("weight_kg")} value={data.weight_kg != null ? `${data.weight_kg} kg` : null} />
            <Row label={tFields("dimensions")} value={dimText} />

            {(data.erp_name ?? data.revision) ? (
              <>
                <SectionDivider label={t("product.specs.sectionReferences")} />
                <Row label={tFields("erp_name")} value={data.erp_name} mono />
                <Row label={tFields("revision")} value={data.revision} />
              </>
            ) : null}
          </dl>
        </CardContent>
      </Card>

      {/* Card 2 — Packaging + Aduanas */}
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("product.packaging.title")}</CardTitle>
            <CardDescription>{t("product.packaging.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl>
              <Row label={tFields("qty_x_box")} value={pkg?.qty_x_box} />
              <Row label={tFields("ean_unit")} value={pkg?.ean_unit} mono />
              <Row label={tFields("ean_box")} value={pkg?.ean_box} mono />
              <Row
                label="GTIN (GS1)"
                value={
                  data.gtin ? (
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono">{data.gtin}</span>
                      {data.gtin.length === 13 ? (
                        <span
                          className="rounded-sm bg-green-100 px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-green-700"
                          title="EAN-13 válido"
                        >
                          EAN-13
                        </span>
                      ) : (
                        <span
                          className="rounded-sm bg-muted px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
                          title={`${data.gtin.length} dígitos`}
                        >
                          {data.gtin.length}d
                        </span>
                      )}
                    </span>
                  ) : null
                }
                mono
              />
              <Row label={tFields("moq")} value={pkg?.moq} />
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("product.intrastat.title")}</CardTitle>
            <CardDescription>{t("product.intrastat.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl>
              <Row label={tFields("hs_code")} value={intra?.hs_code} mono />
              <Row label={tFields("origin_country")} value={intra?.origin_country} />
              <Row
                label={tFields("net_weight_kg")}
                value={intra?.net_weight_kg != null ? `${intra.net_weight_kg} kg` : null}
              />
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
