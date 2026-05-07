"use client";

import { useTranslations } from "next-intl";
import { Pencil } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { TranslationStatusPill } from "@/components/domain/translation-status-pill";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { useProduct } from "@/lib/hooks/products/use-product";

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
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">{product.sku}</span>
          {product.family ? (
            <Badge variant="secondary" className="capitalize">
              {product.family}
            </Badge>
          ) : null}
          {!product.active ? (
            <Badge variant="outline" className="text-muted-foreground">
              inactive
            </Badge>
          ) : null}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{product.name_en}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <DataQualityBadge value={product.data_quality} />
          <TranslationStatusPill language="en" status="approved" />
          <TranslationStatusPill language="es" status={product.translation_status_es} />
          <TranslationStatusPill language="ar" status={product.translation_status_ar} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <RbacGuard permissions={["products:write"]}>
          <Button asChild variant="outline" size="sm">
            <Link href={`/catalogo/${product.sku}/edit`}>
              <Pencil className="h-4 w-4" /> {t("actions.edit")}
            </Link>
          </Button>
        </RbacGuard>
        <SkuActionsMenu
          product={{ id: product.id, sku: product.sku, active: product.active }}
        />
      </div>
    </div>
  );
}
