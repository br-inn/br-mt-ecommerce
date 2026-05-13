"use client";

import { useTranslations } from "next-intl";
import { Pencil, Barcode, Ruler, Layers, GitBranch } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { TranslationStatusPill } from "@/components/domain/translation-status-pill";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { useProduct } from "@/lib/hooks/products/use-product";
import { getProductName } from "@/lib/utils/product-display";
import { isProductActive } from "@/lib/utils/product-lifecycle";
import type { ProductLifecycleStatus } from "@/lib/api/endpoints/products";

// SAP Fiori Semantic Colors — lifecycle status (UX-01)
const LIFECYCLE_CONFIG: Record<
  ProductLifecycleStatus,
  { label: string; dotClass: string; badgeVariant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft:        { label: "Borrador",      dotClass: "bg-gray-400",   badgeVariant: "secondary"   },
  in_review:    { label: "En Revisión",   dotClass: "bg-yellow-500", badgeVariant: "outline"     },
  active:       { label: "Activo",        dotClass: "bg-green-500",  badgeVariant: "default"     },
  deprecated:   { label: "Obsoleto",      dotClass: "bg-orange-500", badgeVariant: "outline"     },
  replaced:     { label: "Reemplazado",   dotClass: "bg-orange-400", badgeVariant: "outline"     },
  discontinued: { label: "Discontinuado", dotClass: "bg-red-500",    badgeVariant: "destructive" },
};

function LifecycleStatusBadge({ status }: { status: ProductLifecycleStatus | null | undefined }) {
  if (!status) return null;
  const cfg = LIFECYCLE_CONFIG[status] ?? LIFECYCLE_CONFIG.active;
  return (
    <Badge variant={cfg.badgeVariant} className="gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-full ${cfg.dotClass}`} />
      {cfg.label}
    </Badge>
  );
}

// SAP Fiori Object Page — KVP row (UX-02)
function KVP({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={`text-sm font-semibold truncate ${mono ? "font-mono" : ""}`}>{value ?? "—"}</dd>
    </div>
  );
}

interface Props {
  sku: string;
}

export function ProductHeader({ sku }: Props) {
  const t = useTranslations("catalog");
  const { data: product, isLoading, isError } = useProduct(sku);

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        {t("errors.notFound")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Row 1: identidad + acciones */}
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">
              {product.sku}
              {product.revision ? (
                <span className="ml-1.5 text-[10px] text-muted-foreground/70">· {product.revision}</span>
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
                <GitBranch className="h-3 w-3" /> Variante de {product.parent_sku}
              </Link>
            ) : null}
            {/* UX-01: LifecycleStatusBadge reemplaza el badge binario active/inactive */}
            <LifecycleStatusBadge status={product.lifecycle_status} />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{getProductName(product)}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <DataQualityBadge value={product.data_quality} />
            <TranslationStatusPill language="en" status="approved" />
            <TranslationStatusPill language="es" status={product.translation_status_es} />
            <TranslationStatusPill language="ar" status={product.translation_status_ar} />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <RbacGuard permissions={["products:write"]}>
            <Button asChild variant="outline" size="sm">
              <Link href={`/catalogo/${product.sku}/edit`}>
                <Pencil className="h-4 w-4" /> {t("actions.edit")}
              </Link>
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

      {/* UX-02: Quick Facts — SAP Fiori Object Page KVPs */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-3 lg:grid-cols-6">
        <KVP label="DN" value={product.dn ? `DN ${product.dn}` : null} />
        <KVP label="PN" value={product.pn ? `PN ${product.pn}` : null} />
        <KVP
          label="Bore"
          value={
            product.bore_mm != null
              ? <span className="flex items-center gap-1">{product.bore_mm} mm</span>
              : null
          }
        />
        <KVP
          label="UoM Base"
          value={
            <span className="flex items-center gap-1">
              <Ruler className="h-3 w-3 text-muted-foreground" />
              {product.base_uom ?? "UNIT"}
            </span>
          }
        />
        <KVP label="Marca" value={product.brand ?? (product as { brand_name?: string }).brand_name} />
        <KVP
          label="GTIN"
          value={
            product.gtin
              ? (
                <span className="flex items-center gap-1">
                  <Barcode className="h-3 w-3 text-muted-foreground" />
                  {product.gtin}
                </span>
              )
              : null
          }
          mono
        />
      </dl>
    </div>
  );
}
