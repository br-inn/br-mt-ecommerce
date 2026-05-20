"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Barcode, ChevronLeft, ChevronRight, ImageIcon, Layers, GitBranch, Pencil, Ruler, X, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

  // Inline edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editDraft, setEditDraft] = useState({
    lifecycle_status: "",
    gtin: "",
    name_en: "",
  });
  const [isSaving, setIsSaving] = useState(false);

  // Sync draft when product loads or edit mode opens
  useEffect(() => {
    if (product) {
      setEditDraft({
        lifecycle_status: product.lifecycle_status ?? "",
        gtin: (product as { gtin?: string | null }).gtin ?? "",
        name_en: (product as { name_en?: string | null }).name_en ?? "",
      });
    }
  }, [product]);

  async function handleSave() {
    setIsSaving(true);
    try {
      await fetch(`/api/v1/products/${sku}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lifecycle_status: editDraft.lifecycle_status || undefined,
          gtin: editDraft.gtin || undefined,
          name_en: editDraft.name_en || undefined,
        }),
      });
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }

  // B2 — prev/next nav desde el catálogo
  const [navSkus, setNavSkus] = useState<string[]>([]);
  // Return-to URL set by other modules (e.g. Amazon listing detail)
  const [returnUrl, setReturnUrl] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("mt-catalog-nav");
      if (raw) setNavSkus(JSON.parse(raw) as string[]);
    } catch {
      // ignore — sessionStorage unavailable o contenido inválido
    }
    try {
      const ret = sessionStorage.getItem("mt-catalog-return");
      if (ret) setReturnUrl(ret);
    } catch {
      // ignore
    }
  }, []);

  const navIdx = navSkus.indexOf(sku);
  const prevSku = navIdx > 0 ? navSkus[navIdx - 1] : null;
  const nextSku = navIdx >= 0 && navIdx < navSkus.length - 1 ? navSkus[navIdx + 1] : null;
  const showNav = navSkus.length > 0 && navIdx >= 0;

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

      {/* Return-to banner — shown when arriving from another module (e.g. Amazon listing) */}
      {returnUrl ? (
        <div className="mb-2 flex items-center gap-2 text-[11.5px] text-muted-foreground">
          <Link
            href={returnUrl}
            onClick={() => {
              try { sessionStorage.removeItem("mt-catalog-return"); } catch { /* ignore */ }
            }}
            className="flex items-center gap-1 rounded-md border px-2.5 py-1 transition-colors hover:text-foreground"
          >
            <ChevronLeft className="size-3.5" />
            Volver al listing Amazon
          </Link>
        </div>
      ) : null}

      {/* B2 — Prev/Next navigation bar */}
      {showNav ? (
        <div className="mb-2 flex items-center gap-3 text-[11.5px] text-muted-foreground">
          <Link href="/catalogo" className="transition-colors hover:text-foreground">
            ← Catálogo
          </Link>
          <span className="opacity-20">|</span>
          {prevSku ? (
            <Link
              href={`/catalogo/${prevSku}`}
              className="flex items-center gap-0.5 font-mono transition-colors hover:text-foreground"
            >
              <ChevronLeft className="size-3.5" />
              {prevSku}
            </Link>
          ) : (
            <span className="flex items-center gap-0.5 opacity-30">
              <ChevronLeft className="size-3.5" />—
            </span>
          )}
          <span className="tabular-nums">
            {navIdx + 1} / {navSkus.length}
          </span>
          {nextSku ? (
            <Link
              href={`/catalogo/${nextSku}`}
              className="flex items-center gap-0.5 font-mono transition-colors hover:text-foreground"
            >
              {nextSku}
              <ChevronRight className="size-3.5" />
            </Link>
          ) : (
            <span className="flex items-center gap-0.5 opacity-30">
              —<ChevronRight className="size-3.5" />
            </span>
          )}
        </div>
      ) : null}

      {/* Layout principal: imagen izquierda + datos derecha */}
      <div className="flex gap-5">
        {/* ── Imagen del producto ── */}
        <div className="shrink-0">
          {product.primary_image_url ? (
            <img
              src={product.primary_image_url}
              alt={getProductName(product)}
              fetchPriority="high"
              decoding="async"
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
                {isEditing ? null : (
                  <LifecycleStatusBadge status={product.lifecycle_status} />
                )}
              </div>

              {/* Nombre + completeness ring */}
              <div className="flex items-center gap-3">
                {isEditing ? (
                  <Input
                    value={editDraft.name_en}
                    onChange={(e) =>
                      setEditDraft((prev) => ({ ...prev, name_en: e.target.value }))
                    }
                    placeholder="Name (EN)"
                    className="h-8 text-xl font-semibold"
                    disabled={isSaving}
                  />
                ) : (
                  <h1 className="text-2xl font-semibold tracking-tight">
                    {getProductName(product)}
                  </h1>
                )}
                <CompletenessRing product={product} />
              </div>

              {/* Data quality badge — solo lectura */}
              <div className="flex flex-wrap items-center gap-2">
                <DataQualityBadge value={product.data_quality} />
              </div>

              {/* Inline edit fields — lifecycle_status + gtin */}
              {isEditing ? (
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Select
                    value={editDraft.lifecycle_status}
                    onValueChange={(v) =>
                      setEditDraft((prev) => ({ ...prev, lifecycle_status: v }))
                    }
                    disabled={isSaving}
                  >
                    <SelectTrigger className="h-7 w-[140px] text-xs">
                      <SelectValue placeholder="Lifecycle status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="discontinued">Discontinued</SelectItem>
                      <SelectItem value="end_of_life">End of Life</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    value={editDraft.gtin}
                    onChange={(e) =>
                      setEditDraft((prev) => ({ ...prev, gtin: e.target.value }))
                    }
                    placeholder="GTIN"
                    className="h-7 w-[160px] font-mono text-xs"
                    disabled={isSaving}
                  />
                </div>
              ) : null}
            </div>

            {/* Botones de acción */}
            <div className="flex shrink-0 items-center gap-2">
              {isEditing ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setIsEditing(false)}
                    disabled={isSaving}
                  >
                    <X className="h-4 w-4" />
                    Cancelar
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={isSaving}
                  >
                    <Check className="h-4 w-4" />
                    {isSaving ? "Guardando…" : "Guardar"}
                  </Button>
                </>
              ) : (
                <RbacGuard permissions={["products:write"]}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsEditing(true)}
                  >
                    <Pencil className="h-4 w-4" />
                    Editar inline
                  </Button>
                </RbacGuard>
              )}
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
