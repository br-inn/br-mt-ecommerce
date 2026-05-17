"use client";

import { useState } from "react";
import Link from "next/link";
import { Barcode, ImageIcon, Layers, GitBranch, Pencil, Ruler } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import { CompletenessRing } from "@/components/ui/completeness-ring";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { ProductEditDrawer } from "@/components/domain/product-edit-drawer";
import { useProduct } from "@/lib/hooks/products/use-product";
import { getProductName } from "@/lib/utils/product-display";
import { isProductActive } from "@/lib/utils/product-lifecycle";

// KVP row — SAP Fiori Object Page pattern (UX-02)
function KVP({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd
        className={`truncate text-sm font-semibold ${mono ? "font-mono" : ""}`}
      >
        {value ?? "—"}
      </dd>
    </div>
  );
}

interface Props {
  sku: string;
}

export function ProductHeader({ sku }: Props) {
  const { data: product, isLoading, isError } = useProduct(sku);
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex gap-4">
        <Skeleton className="h-[140px] w-[140px] shrink-0 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        No se encontró el producto.
      </div>
    );
  }

  const seriesLabel =
    product.series_detail?.code ??
    (product as { series?: string | null }).series ??
    null;

  return (
    <>
      {/* Drawer de edición unificado */}
      <ProductEditDrawer
        sku={sku}
        product={product}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />

      {/* Layout principal: imagen izquierda + datos derecha */}
      <div className="flex gap-5">
        {/* ── Imagen del producto ── */}
        <div className="shrink-0">
          {product.primary_image_url ? (
            <img
              src={product.primary_image_url}
              alt={getProductName(product)}
              className="h-[140px] w-[140px] rounded-lg object-cover"
              style={{ border: "1px solid hsl(var(--border))" }}
            />
          ) : (
            <div
              className="flex h-[140px] w-[140px] items-center justify-center rounded-lg"
              style={{ border: "1px solid hsl(var(--border))", background: "hsl(var(--muted)/0.4)" }}
            >
              <ImageIcon className="h-10 w-10 text-muted-foreground/25" strokeWidth={1.2} />
            </div>
          )}
        </div>

        {/* ── Datos del producto ── */}
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          {/* Fila 1: identidad + acciones */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1">
              {/* SKU + revision + badges de clasificación */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {product.sku}
                  {product.revision ? (
                    <span className="ml-1.5 text-[10px] text-muted-foreground/60">
                      · {product.revision}
                    </span>
                  ) : null}
                </span>
                {product.family ? (
                  <Badge variant="secondary" className="capitalize">
                    {product.family}
                  </Badge>
                ) : null}
                {product.is_parent ? (
                  <Badge variant="outline" className="gap-1 text-[11px]">
                    <Layers className="h-3 w-3" /> Padre
                  </Badge>
                ) : null}
                {product.is_variant && product.parent_sku ? (
                  <Link
                    href={`/catalogo/${product.parent_sku}`}
                    className="inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-[11px] font-semibold text-foreground transition-colors hover:bg-muted/50"
                  >
                    <GitBranch className="h-3 w-3" /> Variante de{" "}
                    {product.parent_sku}
                  </Link>
                ) : null}
                <LifecycleStatusBadge status={product.lifecycle_status} />
              </div>

              {/* Nombre + completeness ring */}
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {getProductName(product)}
                </h1>
                <CompletenessRing product={product} />
              </div>

              {/* Data quality badge — solo lectura */}
              <div className="flex flex-wrap items-center gap-2">
                <DataQualityBadge value={product.data_quality} />
              </div>
            </div>

            {/* Botones de acción */}
            <div className="flex shrink-0 items-center gap-2">
              <RbacGuard permissions={["products:write"]}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDrawerOpen(true)}
                >
                  <Pencil className="h-4 w-4" />
                  Editar
                </Button>
              </RbacGuard>
              <SkuActionsMenu
                product={{
                  id: (product as { id?: string }).id ?? product.internal_id,
                  sku: product.sku,
                  active: isProductActive(product),
                }}
              />
            </div>
          </div>

          {/* Fila 2: Quick Facts (KVPs) */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-4">
            <KVP
              label="UoM Base"
              value={
                <span className="flex items-center gap-1">
                  <Ruler className="h-3 w-3 text-muted-foreground" />
                  {product.base_uom ?? "UNIT"}
                </span>
              }
            />
            <KVP
              label="GTIN"
              value={
                product.gtin ? (
                  <span className="flex items-center gap-1">
                    <Barcode className="h-3 w-3 text-muted-foreground" />
                    {product.gtin}
                  </span>
                ) : null
              }
              mono
            />
            <KVP
              label="Marca"
              value={
                product.brand ??
                (product as { brand_name?: string }).brand_name
              }
            />
            <KVP label="Serie" value={seriesLabel} />
            {product.model_detail ? (
              <>
                <KVP
                  label="Modelo"
                  value={
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono">
                        {product.model_detail.code}
                      </span>
                      {product.model_detail.color_label ? (
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {product.model_detail.color_label}
                        </Badge>
                      ) : null}
                    </span>
                  }
                />
                {product.model_detail.connection_type ? (
                  <KVP
                    label="Conexión"
                    value={product.model_detail.connection_type}
                  />
                ) : null}
              </>
            ) : null}
          </dl>
        </div>
      </div>
    </>
  );
}
