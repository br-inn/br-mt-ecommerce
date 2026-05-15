"use client";

import { useState } from "react";
import type React from "react";
import { useTranslations } from "next-intl";
import { Pencil, Barcode, Ruler, Layers, GitBranch } from "lucide-react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
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
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import { CompletenessRing } from "@/components/ui/completeness-ring";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { TranslationStatusPill } from "@/components/domain/translation-status-pill";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { useProduct } from "@/lib/hooks/products/use-product";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api/endpoints/products";
import { productKeys } from "@/lib/hooks/products/query-keys";
import { getProductName } from "@/lib/utils/product-display";
import { isProductActive } from "@/lib/utils/product-lifecycle";
import type { ProductLifecycleStatus, DataQuality } from "@/lib/api/endpoints/products";
import { usePatchDataQuality } from "@/lib/hooks/products/use-patch-data-quality";

// SAP Fiori Object Page — KVP row (UX-02)
function KVP({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={`text-sm font-semibold truncate ${mono ? "font-mono" : ""}`}>{value ?? "—"}</dd>
    </div>
  );
}

const LIFECYCLE_OPTIONS: ProductLifecycleStatus[] = [
  "draft", "in_review", "active", "deprecated", "replaced", "discontinued",
];

interface Props {
  sku: string;
}

export function ProductHeader({ sku }: Props) {
  const t = useTranslations("catalog");
  const queryClient = useQueryClient();
  const { data: product, isLoading, isError } = useProduct(sku);

  const [editMode, setEditMode] = useState(false);
  const [draft, setDraft] = useState<{
    name_es: string;
    brand: string;
    gtin: string;
    lifecycle_status: ProductLifecycleStatus;
  } | null>(null);

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => productsApi.update(sku, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.detail(sku) });
      setEditMode(false);
      setDraft(null);
    },
  });

  const patchQuality = usePatchDataQuality(sku);

  const enterEdit = () => {
    if (!product) return;
    setDraft({
      name_es: (product.translations?.es?.name ?? "") as string,
      brand: product.brand ?? "",
      gtin: product.gtin ?? "",
      lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
    });
    setEditMode(true);
  };

  const cancelEdit = () => {
    setEditMode(false);
    setDraft(null);
  };

  const saveEdit = () => {
    if (!draft) return;
    patchMutation.mutate({
      brand: draft.brand || null,
      gtin: draft.gtin || null,
      lifecycle_status: draft.lifecycle_status,
    });
  };

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

  const seriesLabel =
    product.series_detail?.code ?? (product as { series?: string | null }).series ?? null;

  return (
    <div className="flex flex-col gap-4">
      {/* Row 1: identidad + acciones */}
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1.5 flex-1 min-w-0">
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
            {editMode && draft ? (
              <Select
                value={draft.lifecycle_status}
                onValueChange={(v) =>
                  setDraft((d) => d ? { ...d, lifecycle_status: v as ProductLifecycleStatus } : d)
                }
              >
                <SelectTrigger className="h-7 w-36 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LIFECYCLE_OPTIONS.map((opt) => (
                    <SelectItem key={opt} value={opt} className="text-xs capitalize">
                      {opt.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <LifecycleStatusBadge status={product.lifecycle_status} />
            )}
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{getProductName(product)}</h1>
            <CompletenessRing product={product} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <DataQualityBadge value={product.data_quality} />
            <RbacGuard permissions={["products:write"]}>
              <select
                value={product.data_quality}
                onChange={(e) =>
                  patchQuality.mutate({ new_value: e.target.value as DataQuality })
                }
                disabled={patchQuality.isPending}
                className="rounded border bg-background px-1 py-0.5 text-xs text-foreground disabled:opacity-50"
                aria-label="Cambiar calidad de datos"
              >
                <option value="partial">Parcial</option>
                <option value="complete">Completa</option>
                <option value="blocked">Bloqueada</option>
              </select>
            </RbacGuard>
            <TranslationStatusPill language="en" status="approved" />
            <TranslationStatusPill language="es" status={product.translation_status_es} />
            <TranslationStatusPill language="ar" status={product.translation_status_ar} />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {editMode ? (
            <>
              <Button
                size="sm"
                onClick={saveEdit}
                disabled={patchMutation.isPending}
              >
                Guardar
              </Button>
              <Button variant="outline" size="sm" onClick={cancelEdit}>
                Cancelar
              </Button>
            </>
          ) : (
            <>
              <RbacGuard permissions={["products:write"]}>
                <Button variant="outline" size="sm" onClick={enterEdit}>
                  <Pencil className="h-4 w-4" /> Editar
                </Button>
              </RbacGuard>
              <RbacGuard permissions={["products:write"]}>
                <Button asChild variant="ghost" size="sm">
                  <Link href={`/catalogo/${product.sku}/edit`}>
                    {t("actions.edit")} completo
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
            </>
          )}
        </div>
      </div>

      {/* UX-02: Quick Facts — 4 KVPs SAP Fiori Object Page */}
      {editMode && draft ? (
        <div className="grid grid-cols-2 gap-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Marca
            </label>
            <Input
              value={draft.brand}
              onChange={(e) => setDraft((d) => d ? { ...d, brand: e.target.value } : d)}
              className="h-7 text-sm"
              placeholder="—"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              GTIN
            </label>
            <Input
              value={draft.gtin}
              onChange={(e) => setDraft((d) => d ? { ...d, gtin: e.target.value } : d)}
              className="h-7 font-mono text-sm"
              placeholder="—"
              maxLength={14}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              UoM Base
            </label>
            <span className="flex h-7 items-center gap-1 text-sm font-semibold text-muted-foreground">
              <Ruler className="h-3 w-3" />
              {product.base_uom ?? "UNIT"}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Serie
            </label>
            <span className="flex h-7 items-center text-sm font-semibold text-muted-foreground">
              {seriesLabel ?? "—"}
            </span>
          </div>
        </div>
      ) : (
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
          <KVP label="Marca" value={product.brand ?? (product as { brand_name?: string }).brand_name} />
          <KVP label="Serie" value={seriesLabel} />
          {product.model_detail ? (
            <>
              <KVP
                label="Modelo"
                value={
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono">{product.model_detail.code}</span>
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
      )}
    </div>
  );
}
