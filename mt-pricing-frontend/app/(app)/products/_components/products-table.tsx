"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { type ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/data/data-table";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { useProducts } from "@/lib/hooks/products/use-products";
import {
  type ProductFilters,
  type ProductListItem,
} from "@/lib/api/endpoints/products";
import { useProductsListFilters } from "./products-filters";

/**
 * Tabla del listado `/products` (Pantalla 2).
 * - Columnas: SKU, name, family, brand, dn, pn, material, status (active).
 * - Filtros desde URL via `useProductsListFilters`.
 * - Paginación cursor mediante `useProducts` (`useInfiniteQuery`).
 * - Errores se muestran inline + toast.
 */
export function ProductsTable() {
  const t = useTranslations("catalog");
  const tCommon = useTranslations("common");
  const { filters: urlFilters } = useProductsListFilters();

  const filters: ProductFilters = React.useMemo(
    () => ({
      family: urlFilters.family,
      search: urlFilters.search,
      data_quality: urlFilters.data_quality,
      active: urlFilters.active,
      dn: urlFilters.dn,
      pn: urlFilters.pn,
      material: urlFilters.material,
      created_after: urlFilters.created_after,
      created_before: urlFilters.created_before,
    }),
    [
      urlFilters.family,
      urlFilters.search,
      urlFilters.data_quality,
      urlFilters.active,
      urlFilters.dn,
      urlFilters.pn,
      urlFilters.material,
      urlFilters.created_after,
      urlFilters.created_before,
    ],
  );

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useProducts(filters);

  React.useEffect(() => {
    if (isError && error) {
      toast.error(t("errors.loadFailed"));
    }
  }, [isError, error, t]);

  const items = React.useMemo<ProductListItem[]>(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  // Filtro client-side por brand (campo no nativo del API en S1; el backend
  // lo añade en S2). Mantiene la URL como source of truth.
  const filteredItems = React.useMemo<ProductListItem[]>(() => {
    if (!urlFilters.brand) return items;
    const needle = urlFilters.brand.toLowerCase();
    return items.filter((it) =>
      ((it as ProductListItem & { brand?: string | null }).brand ?? "")
        .toLowerCase()
        .includes(needle),
    );
  }, [items, urlFilters.brand]);

  const totalLoaded = filteredItems.length;

  const columns = React.useMemo<ColumnDef<ProductListItem>[]>(
    () => [
      {
        id: "sku",
        header: () => <span>{t("columns.sku")}</span>,
        accessorKey: "sku",
        cell: ({ row }) => (
          <Link
            href={`/products/${row.original.sku}`}
            className="font-mono text-xs font-semibold text-primary hover:underline"
            data-testid={`product-row-${row.original.sku}`}
          >
            {row.original.sku}
          </Link>
        ),
      },
      {
        id: "name",
        header: () => <span>{t("columns.name")}</span>,
        accessorKey: "name_en",
        cell: ({ row }) => (
          <span className="line-clamp-1 max-w-xs">{row.original.name_en}</span>
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
        id: "brand",
        header: () => <span>brand</span>,
        cell: ({ row }) => {
          const brand = (row.original as ProductListItem & { brand?: string | null })
            .brand;
          return <span>{brand ?? "—"}</span>;
        },
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
        id: "status",
        header: () => <span>{t("columns.active")}</span>,
        accessorKey: "active",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Badge variant={row.original.active ? "default" : "outline"}>
              {row.original.active
                ? t("filters.active")
                : t("filters.inactive")}
            </Badge>
            <DataQualityBadge value={row.original.data_quality} />
          </div>
        ),
      },
    ],
    [t],
  );

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="products-loading">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card data-testid="products-error">
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
      <Card data-testid="products-empty">
        <CardContent className="flex flex-col items-center gap-2 py-16 text-center">
          <h2 className="text-lg font-semibold">{t("empty.title")}</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            {t("empty.description")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3" data-testid="products-table-root">
      <DataTable<ProductListItem, unknown> columns={columns} data={filteredItems} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span data-testid="products-total-count">
          {t("totalCount", { count: totalLoaded })}
        </span>
        {hasNextPage ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            data-testid="products-load-more"
          >
            {isFetchingNextPage ? tCommon("loading") : t("loadMore")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
