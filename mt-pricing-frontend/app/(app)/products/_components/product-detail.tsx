"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { useProduct } from "@/lib/hooks/products/use-product";
import { type Product } from "@/lib/api/endpoints/products";
import {
  getProductDescription,
  getProductName,
} from "@/lib/utils/product-display";
import { isProductActive } from "@/lib/utils/product-lifecycle";
import { ProductEditForm } from "../[sku]/_components/product-edit-form";
import { ImagesTab } from "../[sku]/_components/images-tab";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { effectiveDisplayApi } from "@/lib/api/endpoints/effective-display";

/**
 * Pantalla 3 — Detalle SKU + tabs.
 * S1: Ficha técnica read-only.
 * S2 (US-1A-02-04-S2): activa tab Imágenes y permite edit inline en Ficha técnica.
 */
export function ProductDetail({ sku }: { sku: string }) {
  const t = useTranslations("catalog");
  const tTabs = useTranslations("catalog.product.tabs");
  const tFields = useTranslations("catalog.product.fields");
  const tEdit = useTranslations("catalog.edit");

  const { data: product, isLoading, isError, error } = useProduct(sku);
  const [editing, setEditing] = React.useState(false);

  React.useEffect(() => {
    if (isError && error) {
      toast.error(t("errors.notFound"));
    }
  }, [isError, error, t]);

  if (isLoading) {
    return (
      <div className="space-y-4" data-testid="product-detail-loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-72 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div
        className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive"
        data-testid="product-detail-error"
      >
        {t("errors.notFound")}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="product-detail-root">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">
            {product.sku}
          </span>
          {product.family ? (
            <Badge variant="secondary" className="capitalize">
              {product.family}
            </Badge>
          ) : null}
          <Badge
            variant={isProductActive(product) ? "default" : "outline"}
            data-testid="product-status-badge"
          >
            {isProductActive(product) ? t("filters.active") : t("filters.inactive")}
          </Badge>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{getProductName(product)}</h1>
      </header>

      {/* Stage 3 (Wave 11) — taxonomy refinement: divisions, series, effective tags/certs, display pair */}
      <Stage3DisplayBlock product={product} />

      <Tabs defaultValue="specs">
        <TabsList>
          <TabsTrigger value="specs" data-testid="tab-specs">
            {tTabs("specs")}
          </TabsTrigger>
          <TabsTrigger value="images" data-testid="tab-images">
            {tTabs("images")}
          </TabsTrigger>
          <TabsTrigger value="translations" disabled title="Sprint 3">
            {tTabs("translations")}
          </TabsTrigger>
          <TabsTrigger value="audit" disabled title="Sprint 3">
            {tTabs("audit")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="specs">
          {editing ? (
            <Card>
              <CardHeader>
                <CardTitle>{tEdit("title")}</CardTitle>
                <CardDescription>{tEdit("subtitle")}</CardDescription>
              </CardHeader>
              <CardContent>
                <ProductEditForm
                  product={product}
                  onCancel={() => setEditing(false)}
                  onSaved={() => setEditing(false)}
                />
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-end">
                <RbacGuard permissions={["products:write"]}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditing(true)}
                    data-testid="product-edit-toggle"
                  >
                    <Pencil className="h-4 w-4" /> {tEdit("editButton")}
                  </Button>
                </RbacGuard>
              </div>
              <ProductSpecsCards product={product} tFields={tFields} />
            </div>
          )}
        </TabsContent>

        <TabsContent value="images">
          <ImagesTab productId={product.sku} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

interface SpecsCardsProps {
  product: Product;
  tFields: (key: string) => string;
}

function ProductSpecsCards({ product, tFields }: SpecsCardsProps) {
  const dim = product.dimensions;
  const dimText = dim
    ? `${dim.length ?? "—"} × ${dim.width ?? "—"} × ${dim.height ?? "—"} ${dim.unit ?? ""}`.trim()
    : "—";
  const pkg = product.packaging;
  const intra = product.intrastat;

  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="product-specs">
      <Card>
        <CardHeader>
          <CardTitle>Identidad</CardTitle>
          <CardDescription>{product.sku}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("sku")} value={product.sku} />
            <Row label={tFields("name_en")} value={getProductName(product)} />
            <Row
              label={tFields("description_en")}
              value={getProductDescription(product)}
            />
            <Row label={tFields("family")} value={product.family} />
            <Row label={tFields("type")} value={product.type} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Especificaciones</CardTitle>
          <CardDescription>DN, PN, material, dimensiones.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("dn")} value={product.dn} />
            <Row label={tFields("pn")} value={product.pn} />
            <Row label={tFields("material")} value={product.material} />
            <Row label={tFields("connection")} value={product.connection} />
            <Row label={tFields("weight_kg")} value={product.weight_kg} />
            <Row label={tFields("dimensions")} value={dimText} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{tFields("packaging")}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("qty_x_box")} value={pkg?.qty_x_box} />
            <Row label={tFields("ean_unit")} value={pkg?.ean_unit} />
            <Row label={tFields("ean_box")} value={pkg?.ean_box} />
            <Row label={tFields("moq")} value={pkg?.moq} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{tFields("intrastat")}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label={tFields("hs_code")} value={intra?.hs_code} />
            <Row label={tFields("origin_country")} value={intra?.origin_country} />
            <Row label={tFields("net_weight_kg")} value={intra?.net_weight_kg} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground sm:w-44">
        {label}
      </dt>
      <dd className="text-sm font-medium">
        {value === null || value === undefined || value === "" ? "—" : value}
      </dd>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Stage 3 (Wave 11) — divisions + series + effective tags/certs + display pair
// ----------------------------------------------------------------------------

interface Stage3Product {
  sku: string;
  series_id?: string | null;
  material_id?: string | null;
  display_pair_sku?: string | null;
  division_codes?: string[];
}

function Stage3DisplayBlock({ product }: { product: Product }) {
  const p = product as Product & Stage3Product;
  const hasStage3Data =
    (p.division_codes && p.division_codes.length > 0) ||
    p.series_id ||
    p.display_pair_sku;

  const effectiveQ = useQuery({
    queryKey: ["effective-display", p.sku],
    queryFn: () => effectiveDisplayApi.get(p.sku),
    staleTime: 30_000,
    retry: 1,
  });

  if (!hasStage3Data && !effectiveQ.data) return null;

  const tags = effectiveQ.data?.tags ?? [];
  const certs = effectiveQ.data?.certifications ?? [];

  return (
    <Card data-testid="product-stage3-block">
      <CardHeader>
        <CardTitle className="text-sm">Catálogo y certificaciones</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {p.division_codes && p.division_codes.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Divisiones:
            </span>
            {p.division_codes.map((code) => (
              <Badge key={code} variant="secondary" className="capitalize">
                {code.replace("_", " ")}
              </Badge>
            ))}
          </div>
        )}
        {p.series_id && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Serie:
            </span>
            <Badge variant="outline" className="font-mono text-[11px]">
              {p.series_id.slice(0, 8)}
            </Badge>
          </div>
        )}
        {p.display_pair_sku && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Modelo emparejado:
            </span>
            <Link
              href={`/catalogo/${encodeURIComponent(p.display_pair_sku)}`}
              className="text-sm font-medium underline-offset-2 hover:underline"
            >
              {p.display_pair_sku}
            </Link>
          </div>
        )}
        {tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Etiquetas:
            </span>
            {tags.map((t) => (
              <Badge key={t} variant="secondary" className="uppercase">
                {t}
              </Badge>
            ))}
          </div>
        )}
        {certs.length > 0 && (
          <div className="space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Certificaciones:
            </span>
            <div className="flex flex-wrap gap-2">
              {certs.map((c) => (
                <span
                  key={c.id}
                  className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                  title={c.scope ?? c.name}
                >
                  {c.logo_url && (
                    <img src={c.logo_url} alt={c.code} className="size-4 object-contain" />
                  )}
                  <span className="font-medium">{c.code}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
