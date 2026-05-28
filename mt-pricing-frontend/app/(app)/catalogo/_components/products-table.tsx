"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { type ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/data/data-table";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { useProducts } from "@/lib/hooks/products/use-products";
import { useToggleProductActive } from "@/lib/hooks/products/use-product-mutations";
import {
  type ProductFilters,
  type ProductListItem,
} from "@/lib/api/endpoints/products";
import { getProductName } from "@/lib/utils/product-display";
import { useCatalogFilters } from "./catalog-filters";
import { useCatalogSearch } from "./catalog-search";

export function ProductsTable() {
  const t = useTranslations("catalog");
  const tCommon = useTranslations("common");
  const { asApi } = useCatalogFilters();
  const { search } = useCatalogSearch();

  const filters: ProductFilters = React.useMemo(
    () => ({
      family: asApi.family,
      data_quality: asApi.data_quality,
      translation_status: asApi.translation_status,
      active: asApi.active,
      search: search.length > 0 ? search : undefined,
    }),
    [asApi.family, asApi.data_quality, asApi.translation_status, asApi.active, search],
  );

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useProducts(filters);

  const toggleActive = useToggleProductActive();

  const items: ProductListItem[] = data?.items ?? [];
  const totalLoaded = items.length;

  const columns = React.useMemo<ColumnDef<ProductListItem>[]>(
    () => [
      {
        id: "sku",
        header: () => <span>{t("columns.sku")}</span>,
        accessorKey: "sku",
        cell: ({ row }) => (
          <Link
            href={`/catalogo/${row.original.sku}`}
            className="font-mono text-xs font-semibold text-primary hover:underline"
          >
            {row.original.sku}
          </Link>
        ),
      },
      {
        id: "name_en",
        header: () => <span>{t("columns.name")}</span>,
        cell: ({ row }) => (
          <span className="line-clamp-1 max-w-xs">
            {getProductName(row.original)}
          </span>
        ),
      },
      {
        id: "family",
        header: () => <span>{t("columns.family")}</span>,
        accessorKey: "family",
        cell: ({ row }) => (
          <span className="capitalize">{row.original.family ?? "—"}</span>
        ),
      },
      {
        id: "dn",
        header: () => <span>{t("columns.dn")}</span>,
        accessorKey: "dn",
        cell: ({ row }) => row.original.dn ?? "—",
      },
      {
        id: "pn",
        header: () => <span>{t("columns.pn")}</span>,
        accessorKey: "pn",
        cell: ({ row }) => row.original.pn ?? "—",
      },
      {
        id: "material",
        header: () => <span>{t("columns.material")}</span>,
        accessorKey: "material",
        cell: ({ row }) => row.original.material ?? "—",
      },
      {
        id: "lifecycle_status",
        header: () => <span>{t("columns.status")}</span>,
        cell: ({ row }) => (
          <LifecycleStatusBadge status={row.original.lifecycle_status} />
        ),
      },
      {
        id: "gtin",
        header: () => <span>GTIN</span>,
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground">
            {row.original.gtin ?? "—"}
          </span>
        ),
      },
      {
        id: "data_quality",
        header: () => <span>{t("columns.dataQuality")}</span>,
        accessorKey: "data_quality",
        cell: ({ row }) => <DataQualityBadge value={row.original.data_quality} />,
      },
      {
        id: "active",
        header: () => <span>{t("columns.active")}</span>,
        accessorKey: "active",
        cell: ({ row }) => {
          const active = row.original.active;
          return (
            <button
              type="button"
              role="switch"
              aria-checked={active}
              aria-label={active ? t("actions.archive") : t("actions.unarchive")}
              onClick={async () => {
                try {
                  await toggleActive.mutateAsync({
                    id:
                      (row.original as ProductListItem & { id?: string }).id ??
                      row.original.internal_id,
                    active: !active,
                  });
                  toast.success(active ? t("actions.deactivated") : t("actions.activated"));
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : tCommon("error"));
                }
              }}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                active ? "bg-emerald-500" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  active ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          );
        },
      },
      {
        id: "actions",
        header: () => <span className="sr-only">{t("columns.actions")}</span>,
        cell: ({ row }) => (
          <SkuActionsMenu
            product={{
              id:
                (row.original as ProductListItem & { id?: string }).id ??
                row.original.internal_id,
              sku: row.original.sku,
              active: row.original.active,
            }}
            compact
          />
        ),
      },
    ],
    [t, tCommon, toggleActive],
  );

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-muted-foreground">{t("errors.loadFailed")}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            {tCommon("retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (totalLoaded === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-16 text-center">
          <h2 className="text-lg font-semibold">{t("empty.title")}</h2>
          <p className="max-w-sm text-sm text-muted-foreground">{t("empty.description")}</p>
          <Button asChild className="mt-2">
            <Link href="/catalogo/nuevo">{t("empty.create")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <DataTable<ProductListItem, unknown> columns={columns} data={items} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{t("totalCount", { count: totalLoaded })}</span>
      </div>
    </div>
  );
}
